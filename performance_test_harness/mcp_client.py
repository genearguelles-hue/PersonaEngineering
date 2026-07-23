"""Minimal Streamable HTTP MCP client for the policy-constrained JMeter tools."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any


PROTOCOL_VERSION = "2025-06-18"


class McpClientError(RuntimeError):
    """The MCP transport or returned tool contract was invalid."""


class JMeterMcpClient:
    def __init__(self, endpoint: str, timeout_seconds: float = 660.0) -> None:
        if not endpoint.startswith(("http://", "https://")):
            raise ValueError("MCP endpoint must use http:// or https://")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be greater than zero")
        self.endpoint = endpoint
        self.timeout_seconds = timeout_seconds
        self.session_id: str | None = None
        self._request_id = 0

    def __enter__(self) -> "JMeterMcpClient":
        self.initialize()
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def initialize(self) -> None:
        if self.session_id is not None:
            return
        response, headers = self._post(
            {
                "jsonrpc": "2.0",
                "id": self._next_id(),
                "method": "initialize",
                "params": {
                    "protocolVersion": PROTOCOL_VERSION,
                    "clientInfo": {
                        "name": "persona-engineering-performance-harness",
                        "version": "0.1.0",
                    },
                    "capabilities": {},
                },
            },
            include_session=False,
        )
        session_id = headers.get("Mcp-Session-Id")
        if not session_id:
            raise McpClientError("MCP initialize response did not provide a session ID")
        if "error" in response:
            raise McpClientError(f"MCP initialize failed: {response['error']}")
        self.session_id = session_id
        self._post(
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            expect_body=False,
        )

    def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        if self.session_id is None:
            self.initialize()
        response, _ = self._post(
            {
                "jsonrpc": "2.0",
                "id": self._next_id(),
                "method": "tools/call",
                "params": {"name": name, "arguments": arguments},
            }
        )
        if "error" in response:
            raise McpClientError(f"MCP tool call failed: {response['error']}")
        try:
            content = response["result"]["content"]
            text = next(item["text"] for item in content if item.get("type") == "text")
            payload = json.loads(text)
        except (KeyError, StopIteration, TypeError, json.JSONDecodeError) as exc:
            raise McpClientError("MCP tool returned an invalid content envelope") from exc
        if not isinstance(payload, dict):
            raise McpClientError("MCP tool payload must be a JSON object")
        return payload

    def close(self) -> None:
        if self.session_id is None:
            return
        request = urllib.request.Request(
            self.endpoint,
            method="DELETE",
            headers=self._headers(include_session=True),
        )
        try:
            urllib.request.urlopen(request, timeout=self.timeout_seconds).close()
        except (urllib.error.URLError, OSError):
            pass
        finally:
            self.session_id = None

    def _post(
        self,
        payload: dict[str, Any],
        *,
        include_session: bool = True,
        expect_body: bool = True,
    ) -> tuple[dict[str, Any], Any]:
        request = urllib.request.Request(
            self.endpoint,
            data=json.dumps(payload, separators=(",", ":")).encode("utf-8"),
            method="POST",
            headers=self._headers(include_session=include_session),
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                body = response.read().decode("utf-8")
                headers = response.headers
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:1000]
            raise McpClientError(f"MCP HTTP {exc.code}: {detail}") from exc
        except (urllib.error.URLError, OSError) as exc:
            raise McpClientError(f"Unable to reach MCP endpoint: {exc}") from exc

        if not expect_body:
            return {}, headers
        return self._decode_response(body), headers

    def _headers(self, *, include_session: bool) -> dict[str, str]:
        headers = {
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json",
            "MCP-Protocol-Version": PROTOCOL_VERSION,
        }
        if include_session and self.session_id:
            headers["Mcp-Session-Id"] = self.session_id
        return headers

    @staticmethod
    def _decode_response(body: str) -> dict[str, Any]:
        candidates = [
            line[6:]
            for line in body.splitlines()
            if line.startswith("data: ") and line[6:] != "[DONE]"
        ]
        raw = candidates[0] if candidates else body
        try:
            response = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise McpClientError("MCP endpoint returned invalid JSON/SSE") from exc
        if not isinstance(response, dict) or response.get("jsonrpc") != "2.0":
            raise McpClientError("MCP endpoint returned an invalid JSON-RPC envelope")
        return response

    def _next_id(self) -> int:
        self._request_id += 1
        return self._request_id
