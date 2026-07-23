"""PE-owned coordinator for MCP-ordered JMeter runs and Ledger evidence."""

from __future__ import annotations

import re
import secrets
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol

from performance_test_harness.assessment import (
    ASSESSMENT_SCHEMA_VERSION,
    METRICS_SCHEMA_VERSION,
    PerformancePolicy,
    assess_metrics,
    validate_metrics,
)
from performance_test_harness.ledger_writer import (
    DEFAULT_LEDGER_PATH,
    append_performance_run_event,
)
from performance_test_harness.reporting import (
    DEFAULT_REPORTS_DIR,
    generate_performance_run_report,
)


EVENT_SCHEMA_VERSION = "pe.performance.run.event.v2"
MCP_SCHEMA_VERSION = "pe.jmeter.mcp.v1"
CLI_SCHEMA_VERSION = "pe.jmeter.cli.v1"
EVIDENCE_SCHEMA_VERSION = "pe.jmeter.evidence.v1"
REPORT_SCHEMA_VERSION = "pe.performance.report.v1"
RUN_ID_RE = re.compile(r"^[a-f0-9]{8,32}$")
PLAN_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*\.jmx$")
PROPERTY_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_.-]{0,127}$")


class ToolClient(Protocol):
    def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]: ...


class CoordinatorError(RuntimeError):
    """A PE performance run could not complete with trusted evidence."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class PerformanceRunCoordinator:
    def __init__(
        self,
        client: ToolClient,
        *,
        ledger_path: Path = DEFAULT_LEDGER_PATH,
        initiator: str = "persona-engineering.performance-test-harness",
        policy: PerformancePolicy | None = None,
        reports_dir: Path = DEFAULT_REPORTS_DIR,
    ) -> None:
        self.client = client
        self.ledger_path = Path(ledger_path)
        self.initiator = initiator
        self.policy = policy or PerformancePolicy()
        self.reports_dir = Path(reports_dir)

    def run(
        self,
        *,
        plan: str,
        run_id: str | None = None,
        properties: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        run_id = run_id or secrets.token_hex(8)
        properties = dict(properties or {})
        self._validate_request(plan, run_id, properties)
        correlation_id = str(uuid.uuid4())
        base = {
            "schema_version": EVENT_SCHEMA_VERSION,
            "run_id": run_id,
            "correlation_id": correlation_id,
            "initiator": {"component": self.initiator},
            "plan": plan,
            "property_names": sorted(properties),
            "contracts": {
                "mcp": MCP_SCHEMA_VERSION,
                "executor": CLI_SCHEMA_VERSION,
                "evidence": EVIDENCE_SCHEMA_VERSION,
                "metrics": METRICS_SCHEMA_VERSION,
                "assessment": ASSESSMENT_SCHEMA_VERSION,
                "report": REPORT_SCHEMA_VERSION,
            },
        }
        self._record(base, "performance.run.requested", "requested", 1)
        self._record(base, "performance.run.started", "running", 2)

        try:
            run_response = self.client.call_tool(
                "jmeter_run",
                {"plan": plan, "run_id": run_id, "properties": properties},
            )
            run_result = self._trusted_result(run_response, "jmeter_run")
            status = str(run_result.get("status", "error"))
            terminal_type = self._terminal_type(status)
            terminal_extra: dict[str, Any] = {
                "executor_timing": {
                    "started_at_epoch": run_result.get("started_at"),
                    "finished_at_epoch": run_result.get("finished_at"),
                    "duration_seconds": run_result.get("duration_seconds"),
                    "return_code": run_result.get("returncode"),
                }
            }

            manifest_response = self.client.call_tool(
                "jmeter_artifact_manifest", {"run_id": run_id}
            )
            manifest = self._trusted_result(
                manifest_response, "jmeter_artifact_manifest"
            )
            self._validate_manifest(manifest, run_id)
            terminal_extra["evidence"] = manifest

            if status == "completed" and not run_response.get("ok"):
                raise CoordinatorError("Completed executor result used a failed MCP envelope")
            if status not in {"completed", "failed", "timed_out", "error"}:
                raise CoordinatorError(f"Unsupported JMeter terminal status: {status}")

            assessment: dict[str, Any] | None = None
            if status == "completed":
                metrics_response = self.client.call_tool(
                    "jmeter_metrics_summary", {"run_id": run_id}
                )
                metrics = self._trusted_result(
                    metrics_response, "jmeter_metrics_summary"
                )
                validate_metrics(
                    metrics,
                    run_id=run_id,
                    plan=plan,
                    evidence_jtl_sha256=self._evidence_jtl_sha(manifest),
                )
                assessment = assess_metrics(metrics, policy=self.policy)
                terminal_extra["metrics"] = metrics
                terminal_extra["assessment"] = assessment

            terminal = self._record(
                base, terminal_type, status, 3, extra=terminal_extra
            )
            report: dict[str, Any]
            try:
                report = generate_performance_run_report(
                    run_id,
                    ledger_path=self.ledger_path,
                    reports_dir=self.reports_dir,
                )
            except Exception as report_error:
                report = {
                    "ok": False,
                    "error": {
                        "type": type(report_error).__name__,
                        "message": str(report_error)[:1000],
                    },
                }
            return {
                "ok": status == "completed",
                "schema_version": "pe.performance.run.result.v1",
                "run_id": run_id,
                "correlation_id": correlation_id,
                "status": status,
                "terminal_event_id": terminal["event_id"],
                "ledger_path": str(self.ledger_path),
                "assessment_verdict": (
                    assessment["verdict"] if assessment is not None else None
                ),
                "performance_accepted": (
                    assessment["verdict"] == "pass"
                    if assessment is not None
                    else False
                ),
                "report": report,
            }
        except Exception as exc:
            error = exc if isinstance(exc, CoordinatorError) else CoordinatorError(str(exc))
            safe_message = self._redact(str(error), properties)
            self._record(
                base,
                "performance.run.error",
                "error",
                3,
                extra={
                    "error": {
                        "type": type(error).__name__,
                        "message": safe_message[:1000],
                    }
                },
            )
            raise error

    def _record(
        self,
        base: dict[str, Any],
        event_type: str,
        status: str,
        sequence: int,
        *,
        extra: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        event = {
            **base,
            "event_id": str(uuid.uuid4()),
            "event_type": event_type,
            "sequence": sequence,
            "occurred_at": _now(),
            "recorded_at": _now(),
            "status": status,
            **(extra or {}),
        }
        return append_performance_run_event(event, self.ledger_path)

    @staticmethod
    def _validate_request(
        plan: str, run_id: str, properties: dict[str, str]
    ) -> None:
        if not PLAN_RE.fullmatch(plan):
            raise ValueError("plan must be a simple .jmx filename")
        if not RUN_ID_RE.fullmatch(run_id):
            raise ValueError("run_id must contain 8-32 lowercase hexadecimal characters")
        for name, value in properties.items():
            if not isinstance(name, str) or not PROPERTY_RE.fullmatch(name):
                raise ValueError(f"invalid JMeter property name: {name!r}")
            if not isinstance(value, str):
                raise ValueError("JMeter property values must be strings")

    @staticmethod
    def _trusted_result(response: dict[str, Any], tool: str) -> dict[str, Any]:
        if response.get("schema_version") != MCP_SCHEMA_VERSION:
            raise CoordinatorError("Unsupported JMeter MCP schema version")
        if response.get("tool") != tool:
            raise CoordinatorError("JMeter MCP tool identity does not match request")
        executor = response.get("executor", {})
        if executor.get("schema_version") != CLI_SCHEMA_VERSION:
            raise CoordinatorError("Unsupported JMeter executor schema version")
        result = response.get("result")
        if not isinstance(result, dict):
            error = response.get("error", {})
            raise CoordinatorError(
                f"{tool} failed: {error.get('type', 'unknown')}: "
                f"{error.get('message', 'no result')}"
            )
        return result

    @staticmethod
    def _validate_manifest(manifest: dict[str, Any], run_id: str) -> None:
        if manifest.get("schema_version") != EVIDENCE_SCHEMA_VERSION:
            raise CoordinatorError("Unsupported JMeter evidence schema version")
        if manifest.get("run_id") != run_id:
            raise CoordinatorError("Evidence manifest run_id does not match")
        artifacts = manifest.get("artifacts")
        if not isinstance(artifacts, dict) or not artifacts:
            raise CoordinatorError("Evidence manifest has no artifacts")
        for name, artifact in artifacts.items():
            if not isinstance(artifact, dict):
                raise CoordinatorError(f"Invalid evidence record: {name}")
            if artifact.get("exists"):
                digest = artifact.get("sha256")
                if not isinstance(digest, str) or not re.fullmatch(r"[a-f0-9]{64}", digest):
                    raise CoordinatorError(f"Invalid artifact hash: {name}")

    @staticmethod
    def _evidence_jtl_sha(manifest: dict[str, Any]) -> str:
        jtl = manifest["artifacts"].get("jtl")
        if not isinstance(jtl, dict) or not jtl.get("exists"):
            raise CoordinatorError("Evidence manifest has no JTL artifact")
        digest = jtl.get("sha256")
        if not isinstance(digest, str) or not re.fullmatch(r"[a-f0-9]{64}", digest):
            raise CoordinatorError("Evidence manifest has an invalid JTL hash")
        return digest

    @staticmethod
    def _terminal_type(status: str) -> str:
        return {
            "completed": "performance.run.completed",
            "failed": "performance.run.failed",
            "timed_out": "performance.run.timed_out",
            "error": "performance.run.error",
        }.get(status, "performance.run.error")

    @staticmethod
    def _redact(message: str, properties: dict[str, str]) -> str:
        redacted = message
        for value in sorted(properties.values(), key=len, reverse=True):
            if value:
                redacted = redacted.replace(value, "<redacted>")
        return redacted
