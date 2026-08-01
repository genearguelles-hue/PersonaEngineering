from __future__ import annotations

from dataclasses import asdict, dataclass
from decimal import Decimal
from typing import Any, Iterable


PRIMARY_CATEGORIES = {"task", "governance", "repair"}
ALL_CATEGORIES = PRIMARY_CATEGORIES | {"evaluation"}


class TokenTelemetryError(ValueError):
    """Raised when provider usage is absent or internally inconsistent."""


@dataclass(frozen=True)
class TokenPricing:
    input_per_million: Decimal | None = None
    cached_input_per_million: Decimal | None = None
    cache_write_input_per_million: Decimal | None = None
    output_per_million: Decimal | None = None
    source: str | None = None

    def configured(self) -> bool:
        return self.input_per_million is not None and self.output_per_million is not None


@dataclass(frozen=True)
class ProviderTokenUsage:
    schema_version: str
    pair_id: str
    arm: str
    call_id: str
    call_category: str
    included_in_primary_total: bool
    provider: str
    provider_reported: bool
    response_id: str
    model: str
    input_tokens: int
    cached_input_tokens: int
    cache_write_input_tokens: int
    output_tokens: int
    reasoning_tokens: int
    total_tokens: int
    latency_ms: int
    retry_count: int
    estimated_cost_usd: str | None
    prompt_sha256: str
    output_sha256: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def normalize_openai_usage(
    *,
    pair_id: str,
    arm: str,
    call_id: str,
    call_category: str,
    response: dict[str, Any],
    latency_ms: int,
    retry_count: int,
    prompt_sha256: str,
    output_sha256: str,
    pricing: TokenPricing | None = None,
) -> ProviderTokenUsage:
    if call_category not in ALL_CATEGORIES:
        raise TokenTelemetryError(f"unsupported call category: {call_category}")
    usage = response.get("usage")
    if not isinstance(usage, dict):
        raise TokenTelemetryError("provider response omitted usage")
    details_in = usage.get("input_tokens_details") or {}
    details_out = usage.get("output_tokens_details") or {}
    values = {
        "input_tokens": usage.get("input_tokens"),
        "cached_input_tokens": details_in.get("cached_tokens", 0),
        "cache_write_input_tokens": details_in.get("cache_write_tokens", 0),
        "output_tokens": usage.get("output_tokens"),
        "reasoning_tokens": details_out.get("reasoning_tokens", 0),
        "total_tokens": usage.get("total_tokens"),
    }
    for field, value in values.items():
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise TokenTelemetryError(
                f"provider usage field {field} must be a non-negative integer"
            )
    if values["total_tokens"] != values["input_tokens"] + values["output_tokens"]:
        raise TokenTelemetryError(
            "provider total_tokens does not equal input_tokens + output_tokens"
        )
    if values["cached_input_tokens"] > values["input_tokens"]:
        raise TokenTelemetryError("cached input exceeds reported input")
    if values["cache_write_input_tokens"] > values["input_tokens"]:
        raise TokenTelemetryError("cache-write input exceeds reported input")
    if values["reasoning_tokens"] > values["output_tokens"]:
        raise TokenTelemetryError("reasoning tokens exceed reported output")
    response_id = response.get("id")
    model = response.get("model")
    if not isinstance(response_id, str) or not response_id:
        raise TokenTelemetryError("provider response omitted response id")
    if not isinstance(model, str) or not model:
        raise TokenTelemetryError("provider response omitted model id")
    cost = estimate_cost(values, pricing) if pricing and pricing.configured() else None
    return ProviderTokenUsage(
        schema_version="pe.resume-provider-token-usage.v1",
        pair_id=pair_id,
        arm=arm,
        call_id=call_id,
        call_category=call_category,
        included_in_primary_total=call_category in PRIMARY_CATEGORIES,
        provider="openai",
        provider_reported=True,
        response_id=response_id,
        model=model,
        input_tokens=values["input_tokens"],
        cached_input_tokens=values["cached_input_tokens"],
        cache_write_input_tokens=values["cache_write_input_tokens"],
        output_tokens=values["output_tokens"],
        reasoning_tokens=values["reasoning_tokens"],
        total_tokens=values["total_tokens"],
        latency_ms=latency_ms,
        retry_count=retry_count,
        estimated_cost_usd=(format(cost, ".8f") if cost is not None else None),
        prompt_sha256=prompt_sha256,
        output_sha256=output_sha256,
    )


def estimate_cost(values: dict[str, int], pricing: TokenPricing) -> Decimal:
    million = Decimal(1_000_000)
    cached = values["cached_input_tokens"]
    cache_write = values["cache_write_input_tokens"]
    uncached = max(values["input_tokens"] - cached - cache_write, 0)
    cached_rate = pricing.cached_input_per_million or pricing.input_per_million
    write_rate = pricing.cache_write_input_per_million or pricing.input_per_million
    return (
        Decimal(uncached) * (pricing.input_per_million or Decimal(0))
        + Decimal(cached) * (cached_rate or Decimal(0))
        + Decimal(cache_write) * (write_rate or Decimal(0))
        + Decimal(values["output_tokens"]) * (pricing.output_per_million or Decimal(0))
    ) / million


def aggregate_usage(
    records: Iterable[ProviderTokenUsage],
    *,
    arm: str,
    include_evaluation: bool = False,
) -> dict[str, Any]:
    selected = [
        item
        for item in records
        if item.arm == arm
        and (include_evaluation or item.included_in_primary_total)
    ]
    by_category: dict[str, int] = {}
    for item in selected:
        by_category[item.call_category] = (
            by_category.get(item.call_category, 0) + item.total_tokens
        )
    cost_values = [Decimal(item.estimated_cost_usd) for item in selected if item.estimated_cost_usd]
    return {
        "arm": arm,
        "provider_reported": bool(selected) and all(item.provider_reported for item in selected),
        "call_count": len(selected),
        "input_tokens": sum(item.input_tokens for item in selected),
        "cached_input_tokens": sum(item.cached_input_tokens for item in selected),
        "cache_write_input_tokens": sum(item.cache_write_input_tokens for item in selected),
        "output_tokens": sum(item.output_tokens for item in selected),
        "reasoning_tokens": sum(item.reasoning_tokens for item in selected),
        "total_tokens": sum(item.total_tokens for item in selected),
        "latency_ms": sum(item.latency_ms for item in selected),
        "retry_count": sum(item.retry_count for item in selected),
        "estimated_cost_usd": (
            format(sum(cost_values, Decimal(0)), ".8f")
            if len(cost_values) == len(selected) and selected
            else None
        ),
        "tokens_by_category": dict(sorted(by_category.items())),
    }
