from __future__ import annotations

import hashlib
import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Callable

from .resume_token_telemetry import (
    ProviderTokenUsage,
    TokenPricing,
    normalize_openai_usage,
)


class ResumeProviderError(RuntimeError):
    """Raised when a provider call fails or returns unusable evidence."""


Transport = Callable[[str, dict[str, str], bytes, int], dict[str, Any]]


@dataclass(frozen=True)
class ModelCallResult:
    text: str
    telemetry: ProviderTokenUsage


class OpenAIResponsesProvider:
    endpoint = "https://api.openai.com/v1/responses"

    def __init__(
        self,
        *,
        model: str,
        reasoning_effort: str,
        max_output_tokens: int,
        api_key: str | None = None,
        timeout_seconds: int = 300,
        max_retries: int = 2,
        pricing: TokenPricing | None = None,
        transport: Transport | None = None,
    ) -> None:
        self.model = model
        self.reasoning_effort = reasoning_effort
        self.max_output_tokens = max_output_tokens
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.pricing = pricing
        self.transport = transport or self._http_transport

    def preflight(self) -> None:
        if not self.model.strip():
            raise ResumeProviderError("model id is required")
        if not self.api_key:
            raise ResumeProviderError("OPENAI_API_KEY is not configured")
        if self.max_output_tokens < 256:
            raise ResumeProviderError("max_output_tokens must be at least 256")

    def generate(
        self,
        *,
        pair_id: str,
        arm: str,
        call_id: str,
        call_category: str,
        instructions: str,
        prompt: str,
        output_schema: dict[str, Any] | None = None,
    ) -> ModelCallResult:
        self.preflight()
        request_body = {
            "model": self.model,
            "store": False,
            "reasoning": {"effort": self.reasoning_effort},
            "max_output_tokens": self.max_output_tokens,
            "instructions": instructions,
            "input": [
                {
                    "role": "user",
                    "content": [{"type": "input_text", "text": prompt}],
                }
            ],
            "metadata": {
                "pe_pair_id": pair_id[:64],
                "pe_arm": arm[:64],
                "pe_call_id": call_id[:64],
                "pe_category": call_category[:64],
            },
            "prompt_cache_key": hashlib.sha256(
                f"{pair_id}:{arm}:{call_id}".encode("utf-8")
            ).hexdigest(),
        }
        if output_schema is not None:
            format_name = "".join(
                character if character.isalnum() else "_" for character in call_id
            )[:64]
            request_body["text"] = {
                "format": {
                    "type": "json_schema",
                    "name": format_name,
                    "strict": True,
                    "schema": output_schema,
                }
            }
        encoded = json.dumps(request_body, sort_keys=True).encode("utf-8")
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        started = time.perf_counter()
        response: dict[str, Any] | None = None
        retry_count = 0
        for attempt in range(self.max_retries + 1):
            try:
                response = self.transport(
                    self.endpoint,
                    headers,
                    encoded,
                    self.timeout_seconds,
                )
                break
            except ResumeProviderError:
                if attempt >= self.max_retries:
                    raise
                retry_count += 1
                time.sleep(min(2**attempt, 4))
        latency_ms = round((time.perf_counter() - started) * 1000)
        if response is None:
            raise ResumeProviderError("provider returned no response")
        if response.get("status") != "completed":
            raise ResumeProviderError(
                "provider response was not completed: "
                f"{response.get('status')!r} {response.get('incomplete_details')!r}"
            )
        output_text = self._output_text(response)
        prompt_hash = hashlib.sha256(encoded).hexdigest()
        output_hash = hashlib.sha256(output_text.encode("utf-8")).hexdigest()
        telemetry = normalize_openai_usage(
            pair_id=pair_id,
            arm=arm,
            call_id=call_id,
            call_category=call_category,
            response=response,
            latency_ms=latency_ms,
            retry_count=retry_count,
            prompt_sha256=prompt_hash,
            output_sha256=output_hash,
            pricing=self.pricing,
        )
        return ModelCallResult(text=output_text, telemetry=telemetry)

    @staticmethod
    def _output_text(response: dict[str, Any]) -> str:
        direct = response.get("output_text")
        if isinstance(direct, str) and direct.strip():
            return direct.strip()
        parts: list[str] = []
        for item in response.get("output") or []:
            if not isinstance(item, dict) or item.get("type") != "message":
                continue
            for content in item.get("content") or []:
                if isinstance(content, dict) and content.get("type") == "output_text":
                    value = content.get("text")
                    if isinstance(value, str):
                        parts.append(value)
        text = "\n".join(parts).strip()
        if not text:
            raise ResumeProviderError("provider response contained no output text")
        return text

    @staticmethod
    def _http_transport(
        url: str,
        headers: dict[str, str],
        body: bytes,
        timeout_seconds: int,
    ) -> dict[str, Any]:
        request = urllib.request.Request(url, data=body, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
                raw = response.read()
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:1000]
            raise ResumeProviderError(
                f"OpenAI HTTP {exc.code}: {detail}"
            ) from exc
        except (urllib.error.URLError, TimeoutError) as exc:
            raise ResumeProviderError(f"OpenAI request failed: {exc}") from exc
        try:
            value = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ResumeProviderError("OpenAI response was not valid JSON") from exc
        if not isinstance(value, dict):
            raise ResumeProviderError("OpenAI response must be a JSON object")
        return value
