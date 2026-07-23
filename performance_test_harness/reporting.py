"""Generate reproducible JSON and Markdown reports from the verified Ledger."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

from performance_test_harness.ledger_writer import (
    DEFAULT_LEDGER_PATH,
    verify_performance_run_ledger,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REPORTS_DIR = PROJECT_ROOT / "reports" / "performance"
REPORT_SCHEMA_PATH = PROJECT_ROOT / "schemas" / "performance_report.schema.json"
TERMINAL_TYPES = {
    "performance.run.completed",
    "performance.run.failed",
    "performance.run.timed_out",
    "performance.run.error",
}


class ReportError(RuntimeError):
    """A report could not be generated from trusted Ledger data."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def generate_performance_run_report(
    run_id: str,
    *,
    ledger_path: Path = DEFAULT_LEDGER_PATH,
    reports_dir: Path = DEFAULT_REPORTS_DIR,
) -> dict[str, Any]:
    """Verify the Ledger, select one run, and atomically write JSON/Markdown."""

    ledger_path = Path(ledger_path)
    verification_errors = verify_performance_run_ledger(ledger_path)
    if verification_errors:
        raise ReportError(
            "Cannot report from an invalid Ledger: " + "; ".join(verification_errors)
        )

    events = _events_for_run(ledger_path, run_id)
    if not events:
        raise ReportError(f"No Ledger events found for run: {run_id}")
    terminal = [event for event in events if event.get("event_type") in TERMINAL_TYPES]
    if len(terminal) != 1:
        raise ReportError(
            f"Expected exactly one terminal Ledger event for run {run_id}"
        )
    ordered = sorted(events, key=lambda event: event["sequence"])
    final = terminal[0]
    report = {
        "schema_version": "pe.performance.report.v1",
        "generated_at": _now(),
        "run_id": run_id,
        "correlation_id": final["correlation_id"],
        "plan": final["plan"],
        "status": final["status"],
        "initiator": final["initiator"],
        "contracts": final["contracts"],
        "lifecycle": [
            {
                "sequence": event["sequence"],
                "event_id": event["event_id"],
                "event_type": event["event_type"],
                "occurred_at": event["occurred_at"],
                "status": event["status"],
            }
            for event in ordered
        ],
        "executor_timing": final.get("executor_timing"),
        "evidence": final.get("evidence"),
        "metrics": final.get("metrics"),
        "assessment": final.get("assessment"),
        "error": final.get("error"),
        "ledger_verification": {
            "ok": True,
            "errors": [],
            "terminal_event_hash": final["ledger"]["event_hash"],
        },
    }
    _validate_report(report)

    reports_dir = Path(reports_dir)
    reports_dir.mkdir(parents=True, exist_ok=True)
    json_path = reports_dir / f"jmeter_performance_{run_id}.json"
    markdown_path = reports_dir / f"jmeter_performance_{run_id}.md"
    _atomic_write(
        json_path,
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )
    _atomic_write(markdown_path, _markdown(report))
    return {
        "ok": True,
        "schema_version": "pe.performance.report.result.v1",
        "run_id": run_id,
        "json_path": str(json_path),
        "markdown_path": str(markdown_path),
    }


def _events_for_run(ledger_path: Path, run_id: str) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    with ledger_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                event = json.loads(line)
                if event.get("run_id") == run_id:
                    events.append(event)
    return events


def _validate_report(report: dict[str, Any]) -> None:
    with REPORT_SCHEMA_PATH.open("r", encoding="utf-8") as handle:
        schema = json.load(handle)
    errors = sorted(
        Draft202012Validator(
            schema, format_checker=FormatChecker()
        ).iter_errors(report),
        key=lambda item: list(item.path),
    )
    if errors:
        raise ReportError(
            "Generated report is invalid: "
            + "; ".join(
                f"{'.'.join(str(part) for part in error.path) or '<root>'}: "
                f"{error.message}"
                for error in errors
            )
        )


def _atomic_write(path: Path, content: str) -> None:
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        with temporary.open("w", encoding="utf-8") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        temporary.replace(path)
    finally:
        if temporary.exists():
            temporary.unlink()


def _markdown(report: dict[str, Any]) -> str:
    lines = [
        f"# JMeter Performance Report — `{report['run_id']}`",
        "",
        f"- **Status:** `{report['status']}`",
        f"- **Plan:** `{report['plan']}`",
        f"- **Correlation ID:** `{report['correlation_id']}`",
        f"- **Generated:** `{report['generated_at']}`",
        f"- **Ledger verified:** `true`",
        "",
        "## Lifecycle",
        "",
        "| Sequence | Event | Status | Occurred |",
        "|---:|---|---|---|",
    ]
    lines.extend(
        f"| {event['sequence']} | `{event['event_type']}` | "
        f"`{event['status']}` | `{event['occurred_at']}` |"
        for event in report["lifecycle"]
    )

    metrics = report.get("metrics")
    if metrics:
        summary = metrics["summary"]
        elapsed = summary["elapsed_ms"]
        lines.extend(
            [
                "",
                "## Performance Metrics",
                "",
                "| Metric | Value |",
                "|---|---:|",
                f"| Samples | {summary['sample_count']} |",
                f"| Successful samples | {summary['success_count']} |",
                f"| Errors | {summary['error_count']} |",
                f"| Error rate | {summary['error_rate']:.6f} |",
                f"| Throughput/second | {summary['throughput_per_second']:.6f} |",
                f"| Mean elapsed (ms) | {_display(elapsed['mean'])} |",
                f"| p95 elapsed (ms) | {_display(elapsed['p95'])} |",
                f"| p99 elapsed (ms) | {_display(elapsed['p99'])} |",
                f"| Source JTL SHA-256 | `{metrics['source_jtl']['sha256']}` |",
            ]
        )

    assessment = report.get("assessment")
    if assessment:
        lines.extend(
            [
                "",
                "## Persona Engineering Assessment",
                "",
                f"**Verdict:** `{assessment['verdict']}`  ",
                f"**Policy:** `{assessment['policy']['policy_id']}` "
                f"(`{assessment['policy']['schema_version']}`)",
                "",
                "| Check | Actual | Requirement | Result |",
                "|---|---:|---:|---|",
            ]
        )
        lines.extend(
            f"| `{check['name']}` | {_display(check['actual'])} | "
            f"`{check['operator']} {_display(check['threshold'])}` | "
            f"`{'pass' if check['passed'] else 'fail'}` |"
            for check in assessment["checks"]
        )

    evidence = report.get("evidence")
    if evidence:
        lines.extend(
            [
                "",
                "## Evidence Artifacts",
                "",
                "| Artifact | Bytes | SHA-256 |",
                "|---|---:|---|",
            ]
        )
        lines.extend(
            f"| `{name}` | {_display(artifact['size_bytes'])} | "
            f"`{artifact['sha256'] or 'unavailable'}` |"
            for name, artifact in sorted(evidence["artifacts"].items())
        )

    if report.get("error"):
        lines.extend(
            [
                "",
                "## Terminal Error",
                "",
                f"- **Type:** `{report['error']['type']}`",
                f"- **Message:** {report['error']['message']}",
            ]
        )

    lines.extend(
        [
            "",
            "## Ledger Binding",
            "",
            f"- **Terminal event hash:** "
            f"`{report['ledger_verification']['terminal_event_hash']}`",
            "- This report is derived from a schema-valid, hash-chain-verified Ledger.",
            "- The report is a projection of Ledger evidence, not an independent execution artifact.",
            "",
        ]
    )
    return "\n".join(lines)


def _display(value: Any) -> str:
    return "n/a" if value is None else str(value)
