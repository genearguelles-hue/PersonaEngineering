"""Deterministic Persona Engineering assessment for JMeter metrics."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any


ASSESSMENT_SCHEMA_VERSION = "pe.performance.assessment.v1"
POLICY_SCHEMA_VERSION = "pe.performance.policy.v1"
METRICS_SCHEMA_VERSION = "pe.jmeter.metrics.v1"


class AssessmentError(ValueError):
    """Metrics or policy data could not be assessed safely."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True)
class PerformancePolicy:
    """Versioned thresholds for a basic JMeter service-level assessment."""

    policy_id: str = "pe.jmeter.smoke.baseline"
    min_sample_count: int = 1
    max_error_rate: float = 0.0
    max_p95_elapsed_ms: float = 1000.0
    min_throughput_per_second: float = 0.1

    def __post_init__(self) -> None:
        if not self.policy_id or len(self.policy_id) > 128:
            raise ValueError("policy_id must contain 1-128 characters")
        if self.min_sample_count < 1:
            raise ValueError("min_sample_count must be at least 1")
        for name, value in (
            ("max_error_rate", self.max_error_rate),
            ("max_p95_elapsed_ms", self.max_p95_elapsed_ms),
            ("min_throughput_per_second", self.min_throughput_per_second),
        ):
            if not isinstance(value, (int, float)) or not math.isfinite(value):
                raise ValueError(f"{name} must be a finite number")
            if value < 0:
                raise ValueError(f"{name} must not be negative")
        if self.max_error_rate > 1:
            raise ValueError("max_error_rate must not exceed 1")

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": POLICY_SCHEMA_VERSION,
            "policy_id": self.policy_id,
            "min_sample_count": self.min_sample_count,
            "max_error_rate": float(self.max_error_rate),
            "max_p95_elapsed_ms": float(self.max_p95_elapsed_ms),
            "min_throughput_per_second": float(
                self.min_throughput_per_second
            ),
        }


def validate_metrics(
    metrics: dict[str, Any],
    *,
    run_id: str,
    plan: str,
    evidence_jtl_sha256: str,
) -> None:
    """Validate the metric identity, core invariants, and evidence binding."""

    if metrics.get("schema_version") != METRICS_SCHEMA_VERSION:
        raise AssessmentError("Unsupported JMeter metrics schema version")
    if metrics.get("run_id") != run_id:
        raise AssessmentError("Metrics run_id does not match")
    if metrics.get("plan") != plan:
        raise AssessmentError("Metrics plan does not match")

    source = metrics.get("source_jtl")
    if not isinstance(source, dict):
        raise AssessmentError("Metrics source JTL record is missing")
    digest = source.get("sha256")
    if digest != evidence_jtl_sha256:
        raise AssessmentError("Metrics JTL hash does not match evidence manifest")

    summary = metrics.get("summary")
    if not isinstance(summary, dict):
        raise AssessmentError("Metrics summary is missing")
    integer_fields = ("sample_count", "success_count", "error_count")
    for name in integer_fields:
        value = summary.get(name)
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise AssessmentError(f"Metrics {name} must be a non-negative integer")
    if summary["success_count"] + summary["error_count"] != summary["sample_count"]:
        raise AssessmentError("Metrics sample counts are inconsistent")

    numeric_fields = (
        "error_rate",
        "duration_seconds",
        "throughput_per_second",
    )
    for name in numeric_fields:
        value = summary.get(name)
        if (
            not isinstance(value, (int, float))
            or isinstance(value, bool)
            or not math.isfinite(value)
            or value < 0
        ):
            raise AssessmentError(f"Metrics {name} must be a finite non-negative number")
    if summary["error_rate"] > 1:
        raise AssessmentError("Metrics error_rate must not exceed 1")

    expected_error_rate = (
        summary["error_count"] / summary["sample_count"]
        if summary["sample_count"]
        else 0.0
    )
    if not math.isclose(
        float(summary["error_rate"]), expected_error_rate, abs_tol=0.000001
    ):
        raise AssessmentError("Metrics error_rate is inconsistent with sample counts")

    elapsed = summary.get("elapsed_ms")
    if not isinstance(elapsed, dict) or "p95" not in elapsed:
        raise AssessmentError("Metrics elapsed_ms.p95 is missing")
    p95 = elapsed["p95"]
    if p95 is not None and (
        not isinstance(p95, (int, float))
        or isinstance(p95, bool)
        or not math.isfinite(p95)
        or p95 < 0
    ):
        raise AssessmentError("Metrics elapsed_ms.p95 is invalid")


def assess_metrics(
    metrics: dict[str, Any],
    *,
    policy: PerformancePolicy,
) -> dict[str, Any]:
    """Apply a transparent threshold policy to already trusted metrics."""

    summary = metrics["summary"]
    sample_count = summary["sample_count"]
    p95 = summary["elapsed_ms"]["p95"]
    checks = [
        _check(
            "minimum_sample_count",
            ">=",
            sample_count,
            policy.min_sample_count,
            sample_count >= policy.min_sample_count,
        ),
        _check(
            "maximum_error_rate",
            "<=",
            summary["error_rate"],
            policy.max_error_rate,
            summary["error_rate"] <= policy.max_error_rate,
        ),
        _check(
            "maximum_p95_elapsed_ms",
            "<=",
            p95,
            policy.max_p95_elapsed_ms,
            p95 is not None and p95 <= policy.max_p95_elapsed_ms,
        ),
        _check(
            "minimum_throughput_per_second",
            ">=",
            summary["throughput_per_second"],
            policy.min_throughput_per_second,
            summary["throughput_per_second"]
            >= policy.min_throughput_per_second,
        ),
    ]
    insufficient = sample_count < policy.min_sample_count or p95 is None
    verdict = (
        "insufficient_evidence"
        if insufficient
        else "pass" if all(check["passed"] for check in checks) else "fail"
    )
    return {
        "schema_version": ASSESSMENT_SCHEMA_VERSION,
        "run_id": metrics["run_id"],
        "evaluated_at": _now(),
        "verdict": verdict,
        "source_jtl_sha256": metrics["source_jtl"]["sha256"],
        "policy": policy.as_dict(),
        "checks": checks,
    }


def _check(
    name: str,
    operator: str,
    actual: int | float | None,
    threshold: int | float,
    passed: bool,
) -> dict[str, Any]:
    return {
        "name": name,
        "operator": operator,
        "actual": actual,
        "threshold": threshold,
        "passed": passed,
    }
