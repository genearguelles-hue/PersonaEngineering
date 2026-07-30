from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class ResultContractError(ValueError):
    pass


def normalize_selenium_summary(tool_result: dict[str, Any]) -> dict[str, Any]:
    """Normalize PE test envelopes into the assessor's Selenium vocabulary."""
    if tool_result.get("tool") not in {None, "selenium"}:
        raise ResultContractError("tool result is not a Selenium result")
    summary = tool_result.get("summary")
    if not isinstance(summary, dict):
        raise ResultContractError("Selenium result summary is missing")

    failures = _integer(summary.get("failures", summary.get("failed", 0)), "failures")
    errors = _integer(summary.get("errors", 0), "errors")
    skipped = _integer(summary.get("skipped", 0), "skipped")
    total_value = summary.get("tests", summary.get("total"))
    testcases = summary.get("testcases")
    if total_value is None and isinstance(testcases, list):
        total_value = len(testcases)
    total = _integer(total_value, "tests")

    explicit_passed = summary.get("passed")
    passed = (
        _integer(explicit_passed, "passed")
        if explicit_passed is not None
        else max(0, total - failures - errors - skipped)
    )
    failed = failures + errors

    duration_value = summary.get("duration_seconds")
    duration_source = "summary.duration_seconds"
    if duration_value is None:
        duration_source = "summary.testcases[].time_seconds"
        duration_value = _testcase_duration(testcases)
    duration = _number(duration_value, "duration_seconds")

    if passed + failed + skipped > total:
        raise ResultContractError(
            "Selenium counts are inconsistent: passed + failed + skipped exceeds tests"
        )

    return {
        "schema_version": "pe.selenium-result-summary.v1",
        "total": total,
        "passed": passed,
        "failed": failed,
        "failures": failures,
        "errors": errors,
        "skipped": skipped,
        "duration_seconds": round(duration, 6),
        "duration_source": duration_source,
        "source_schema_version": tool_result.get("schema_version"),
        "source_status": tool_result.get("status"),
    }


def verify_selenium_result_contract(
    tool_result: dict[str, Any],
    *,
    minimum_passed_tests: int,
    maximum_duration_seconds: float,
    require_zero_failures: bool,
) -> dict[str, Any]:
    normalized = normalize_selenium_summary(tool_result)
    checks = [
        {
            "check_id": "selenium.result.status",
            "passed": tool_result.get("status") == "passed",
            "observed": tool_result.get("status"),
            "expected": "passed",
        },
        {
            "check_id": "selenium.zero_failures",
            "passed": not require_zero_failures or normalized["failed"] == 0,
            "observed": normalized["failed"],
            "expected": 0,
        },
        {
            "check_id": "selenium.minimum_passed_tests",
            "passed": normalized["passed"] >= minimum_passed_tests,
            "observed": normalized["passed"],
            "expected": f">={minimum_passed_tests}",
        },
        {
            "check_id": "selenium.maximum_duration_seconds",
            "passed": normalized["duration_seconds"] <= maximum_duration_seconds,
            "observed": normalized["duration_seconds"],
            "expected": f"<={maximum_duration_seconds}",
        },
    ]
    return {
        "schema_version": "pe.selenium-result-contract-verification.v1",
        "valid": all(check["passed"] for check in checks),
        "normalized_summary": normalized,
        "checks": checks,
    }


def load_runtime_tool_result(run_dir_value: Any) -> tuple[Path, dict[str, Any]]:
    if not isinstance(run_dir_value, str) or not run_dir_value.strip():
        raise ResultContractError("authoritative runtime did not report a run_dir")
    run_dir = Path(run_dir_value).expanduser().resolve()
    if not run_dir.is_dir():
        raise ResultContractError(f"authoritative runtime run_dir is missing: {run_dir}")
    candidate = run_dir / "tool-result.json"
    if candidate.is_symlink():
        raise ResultContractError("authoritative runtime tool-result.json may not be a symlink")
    result_path = candidate.resolve()
    if result_path.parent != run_dir or not result_path.is_file():
        raise ResultContractError("authoritative runtime tool-result.json is missing")
    try:
        payload = json.loads(result_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ResultContractError(f"could not read authoritative tool result: {exc}") from exc
    if not isinstance(payload, dict):
        raise ResultContractError("authoritative tool result must be a JSON object")
    return result_path, payload


def _testcase_duration(testcases: Any) -> float:
    if not isinstance(testcases, list) or not testcases:
        return 0.0
    duration = 0.0
    for testcase in testcases:
        if not isinstance(testcase, dict):
            raise ResultContractError("Selenium testcase entries must be objects")
        duration += _number(testcase.get("time_seconds", 0), "testcase.time_seconds")
    return duration


def _integer(value: Any, name: str) -> int:
    if isinstance(value, bool):
        raise ResultContractError(f"{name} must be an integer")
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ResultContractError(f"{name} must be an integer") from exc
    if parsed < 0:
        raise ResultContractError(f"{name} may not be negative")
    return parsed


def _number(value: Any, name: str) -> float:
    if isinstance(value, bool):
        raise ResultContractError(f"{name} must be numeric")
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise ResultContractError(f"{name} must be numeric") from exc
    if parsed < 0:
        raise ResultContractError(f"{name} may not be negative")
    return parsed
