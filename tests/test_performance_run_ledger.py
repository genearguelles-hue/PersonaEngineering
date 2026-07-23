from __future__ import annotations

import json
import tempfile
import unittest
import uuid
from pathlib import Path

from performance_test_harness.assessment import PerformancePolicy
from performance_test_harness.coordinator import (
    CoordinatorError,
    PerformanceRunCoordinator,
)
from performance_test_harness.ledger_writer import (
    append_performance_run_event,
    verify_performance_run_ledger,
)
from performance_test_harness.mcp_client import JMeterMcpClient, McpClientError
from performance_test_harness.reporting import generate_performance_run_report


DIGESTS = {
    name: (str(index) * 64)
    for index, name in enumerate(
        ("test_plan", "jtl", "jmeter_log", "dashboard_index", "run_metadata"),
        start=1,
    )
}


def distribution(p95: float) -> dict[str, float]:
    return {
        "min": 10.0,
        "max": p95,
        "mean": p95 / 2,
        "median": p95 / 2,
        "p90": p95,
        "p95": p95,
        "p99": p95,
    }


def envelope(tool: str, result: dict, *, ok: bool = True) -> dict:
    return {
        "schema_version": "pe.jmeter.mcp.v1",
        "tool": tool,
        "ok": ok,
        "executor": {
            "schema_version": "pe.jmeter.cli.v1",
            "command": tool.removeprefix("jmeter_").replace("_", "-"),
            "exit_code": 0 if ok else 1,
        },
        "result": result,
    }


class FakeMcpClient:
    def __init__(
        self,
        *,
        status: str = "completed",
        bad_manifest: bool = False,
        bad_metrics_hash: bool = False,
        error_count: int = 0,
    ) -> None:
        self.status = status
        self.bad_manifest = bad_manifest
        self.bad_metrics_hash = bad_metrics_hash
        self.error_count = error_count
        self.calls: list[tuple[str, dict]] = []

    def call_tool(self, name: str, arguments: dict) -> dict:
        self.calls.append((name, arguments))
        if name == "jmeter_run":
            return envelope(
                name,
                {
                    "run_id": arguments["run_id"],
                    "plan": arguments["plan"],
                    "status": self.status,
                    "started_at": 100.0,
                    "finished_at": 101.25,
                    "duration_seconds": 1.25,
                    "returncode": 0 if self.status == "completed" else 1,
                },
                ok=self.status == "completed",
            )
        if name == "jmeter_artifact_manifest":
            evidence_schema = "wrong" if self.bad_manifest else "pe.jmeter.evidence.v1"
            return envelope(
                name,
                {
                    "ok": True,
                    "schema_version": evidence_schema,
                    "run_id": arguments["run_id"],
                    "plan": "smoke.jmx",
                    "status": self.status,
                    "generated_at": "2026-07-22T12:00:00Z",
                    "artifacts": {
                        artifact_name: {
                            "path": f"reports/runs/abcdef12/{artifact_name}",
                            "exists": True,
                            "size_bytes": 10 + index,
                            "sha256": digest,
                        }
                        for index, (artifact_name, digest) in enumerate(DIGESTS.items())
                    },
                },
            )
        if name == "jmeter_metrics_summary":
            sample_count = 10
            return envelope(
                name,
                {
                    "ok": True,
                    "schema_version": "pe.jmeter.metrics.v1",
                    "run_id": arguments["run_id"],
                    "plan": "smoke.jmx",
                    "status": self.status,
                    "generated_at": "2026-07-22T12:00:01Z",
                    "source_jtl": {
                        "path": "reports/runs/abcdef12/results.jtl",
                        "exists": True,
                        "size_bytes": 1234,
                        "sha256": (
                            "f" * 64 if self.bad_metrics_hash else DIGESTS["jtl"]
                        ),
                    },
                    "summary": {
                        "sample_count": sample_count,
                        "success_count": sample_count - self.error_count,
                        "error_count": self.error_count,
                        "error_rate": self.error_count / sample_count,
                        "duration_seconds": 0.5,
                        "throughput_per_second": 20.0,
                        "received_bytes": 10000,
                        "sent_bytes": 1000,
                        "response_codes": {
                            "200": sample_count - self.error_count,
                            **({"500": self.error_count} if self.error_count else {}),
                        },
                        "samples_by_label": {"smoke": sample_count},
                        "elapsed_ms": distribution(250.0),
                        "latency_ms": distribution(100.0),
                        "connect_ms": distribution(25.0),
                    },
                },
            )
        raise AssertionError(f"unexpected tool: {name}")


class SecretEchoingFailureClient:
    def call_tool(self, name: str, arguments: dict) -> dict:
        raise RuntimeError(f"remote rejected {arguments['properties']['token']}")


class PerformanceRunLedgerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.ledger = Path(self.temporary.name) / "performance.jsonl"
        self.reports = Path(self.temporary.name) / "reports"

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def events(self) -> list[dict]:
        return [
            json.loads(line)
            for line in self.ledger.read_text(encoding="utf-8").splitlines()
        ]

    def coordinator(self, client: object, **kwargs: object) -> PerformanceRunCoordinator:
        return PerformanceRunCoordinator(
            client,
            ledger_path=self.ledger,
            reports_dir=self.reports,
            **kwargs,
        )

    def test_completed_run_records_ordered_hash_chained_evidence(self) -> None:
        client = FakeMcpClient()
        result = self.coordinator(client).run(
            plan="smoke.jmx",
            run_id="abcdef12",
            properties={"threads": "secret-value", "host": "internal.example"},
        )

        self.assertTrue(result["ok"])
        events = self.events()
        self.assertEqual(
            [event["event_type"] for event in events],
            [
                "performance.run.requested",
                "performance.run.started",
                "performance.run.completed",
            ],
        )
        self.assertEqual([event["sequence"] for event in events], [1, 2, 3])
        self.assertEqual(len({event["run_id"] for event in events}), 1)
        self.assertEqual(len({event["correlation_id"] for event in events}), 1)
        self.assertEqual(events[0]["property_names"], ["host", "threads"])
        serialized = self.ledger.read_text(encoding="utf-8")
        self.assertNotIn("secret-value", serialized)
        self.assertNotIn("internal.example", serialized)
        terminal_artifacts = events[2]["evidence"]["artifacts"]
        self.assertEqual(
            {item["sha256"] for item in terminal_artifacts.values()},
            set(DIGESTS.values()),
        )
        self.assertEqual(events[2]["metrics"]["schema_version"], "pe.jmeter.metrics.v1")
        self.assertEqual(
            events[2]["metrics"]["source_jtl"]["sha256"],
            events[2]["evidence"]["artifacts"]["jtl"]["sha256"],
        )
        self.assertEqual(events[2]["assessment"]["verdict"], "pass")
        self.assertEqual(result["assessment_verdict"], "pass")
        self.assertTrue(result["performance_accepted"])
        self.assertTrue(Path(result["report"]["json_path"]).is_file())
        self.assertTrue(Path(result["report"]["markdown_path"]).is_file())
        self.assertEqual(verify_performance_run_ledger(self.ledger), [])

    def test_failed_executor_still_records_one_terminal_event(self) -> None:
        result = self.coordinator(FakeMcpClient(status="failed")).run(
            plan="smoke.jmx", run_id="deadbeef"
        )

        self.assertFalse(result["ok"])
        events = self.events()
        self.assertEqual(len(events), 3)
        self.assertEqual(events[-1]["event_type"], "performance.run.failed")
        self.assertEqual(events[-1]["status"], "failed")

    def test_threshold_breach_records_failed_assessment_not_failed_execution(
        self,
    ) -> None:
        result = self.coordinator(
            FakeMcpClient(error_count=1),
            policy=PerformancePolicy(max_error_rate=0.0),
        ).run(plan="smoke.jmx", run_id="abcdef12")

        self.assertTrue(result["ok"])
        self.assertFalse(result["performance_accepted"])
        self.assertEqual(result["assessment_verdict"], "fail")
        terminal = self.events()[-1]
        self.assertEqual(terminal["event_type"], "performance.run.completed")
        failed_checks = [
            check["name"]
            for check in terminal["assessment"]["checks"]
            if not check["passed"]
        ]
        self.assertEqual(failed_checks, ["maximum_error_rate"])

    def test_small_run_is_classified_as_insufficient_evidence(self) -> None:
        result = self.coordinator(
            FakeMcpClient(),
            policy=PerformancePolicy(min_sample_count=20),
        ).run(plan="smoke.jmx", run_id="abcdef12")

        self.assertEqual(result["assessment_verdict"], "insufficient_evidence")
        self.assertFalse(result["performance_accepted"])

    def test_metrics_must_bind_to_evidence_jtl_hash(self) -> None:
        with self.assertRaisesRegex(CoordinatorError, "JTL hash"):
            self.coordinator(FakeMcpClient(bad_metrics_hash=True)).run(
                plan="smoke.jmx", run_id="abcdef12"
            )

        events = self.events()
        self.assertEqual(len(events), 3)
        self.assertEqual(events[-1]["event_type"], "performance.run.error")
        self.assertNotIn("metrics", events[-1])

    def test_generated_reports_expose_metrics_verdict_and_ledger_binding(
        self,
    ) -> None:
        result = self.coordinator(FakeMcpClient()).run(
            plan="smoke.jmx", run_id="abcdef12"
        )

        report = json.loads(
            Path(result["report"]["json_path"]).read_text(encoding="utf-8")
        )
        markdown = Path(result["report"]["markdown_path"]).read_text(
            encoding="utf-8"
        )
        self.assertEqual(report["schema_version"], "pe.performance.report.v1")
        self.assertEqual(report["assessment"]["verdict"], "pass")
        self.assertTrue(report["ledger_verification"]["ok"])
        self.assertEqual(
            report["metrics"]["source_jtl"]["sha256"], DIGESTS["jtl"]
        )
        self.assertIn("Persona Engineering Assessment", markdown)
        self.assertIn("Source JTL SHA-256", markdown)
        self.assertIn(report["ledger_verification"]["terminal_event_hash"], markdown)

    def test_v1_history_and_v2_assessed_runs_share_one_verified_chain(self) -> None:
        append_performance_run_event(
            {
                "schema_version": "pe.performance.run.event.v1",
                "event_type": "performance.run.requested",
                "event_id": str(uuid.uuid4()),
                "run_id": "11111111",
                "correlation_id": str(uuid.uuid4()),
                "sequence": 1,
                "occurred_at": "2026-07-22T12:00:00Z",
                "recorded_at": "2026-07-22T12:00:00Z",
                "initiator": {"component": "legacy-harness"},
                "plan": "legacy.jmx",
                "property_names": [],
                "contracts": {
                    "mcp": "pe.jmeter.mcp.v1",
                    "executor": "pe.jmeter.cli.v1",
                    "evidence": "pe.jmeter.evidence.v1",
                },
                "status": "requested",
            },
            self.ledger,
        )

        self.coordinator(FakeMcpClient()).run(
            plan="smoke.jmx", run_id="abcdef12"
        )

        events = self.events()
        self.assertEqual(events[0]["schema_version"], "pe.performance.run.event.v1")
        self.assertEqual(events[-1]["schema_version"], "pe.performance.run.event.v2")
        self.assertEqual(verify_performance_run_ledger(self.ledger), [])

    def test_historical_v1_run_can_be_projected_as_unassessed_report(self) -> None:
        correlation_id = str(uuid.uuid4())
        base = {
            "schema_version": "pe.performance.run.event.v1",
            "run_id": "11111111",
            "correlation_id": correlation_id,
            "initiator": {"component": "legacy-harness"},
            "plan": "legacy.jmx",
            "property_names": [],
            "contracts": {
                "mcp": "pe.jmeter.mcp.v1",
                "executor": "pe.jmeter.cli.v1",
                "evidence": "pe.jmeter.evidence.v1",
            },
        }
        for sequence, event_type, status in (
            (1, "performance.run.requested", "requested"),
            (2, "performance.run.started", "running"),
        ):
            append_performance_run_event(
                {
                    **base,
                    "event_type": event_type,
                    "event_id": str(uuid.uuid4()),
                    "sequence": sequence,
                    "occurred_at": f"2026-07-22T12:00:0{sequence}Z",
                    "recorded_at": f"2026-07-22T12:00:0{sequence}Z",
                    "status": status,
                },
                self.ledger,
            )
        append_performance_run_event(
            {
                **base,
                "event_type": "performance.run.completed",
                "event_id": str(uuid.uuid4()),
                "sequence": 3,
                "occurred_at": "2026-07-22T12:00:03Z",
                "recorded_at": "2026-07-22T12:00:03Z",
                "status": "completed",
                "executor_timing": {
                    "started_at_epoch": 100.0,
                    "finished_at_epoch": 101.0,
                    "duration_seconds": 1.0,
                    "return_code": 0,
                },
                "evidence": {
                    "ok": True,
                    "schema_version": "pe.jmeter.evidence.v1",
                    "run_id": "11111111",
                    "plan": "legacy.jmx",
                    "status": "completed",
                    "generated_at": "2026-07-22T12:00:03Z",
                    "artifacts": {
                        name: {
                            "path": f"reports/runs/11111111/{name}",
                            "exists": True,
                            "size_bytes": 10,
                            "sha256": digest,
                        }
                        for name, digest in DIGESTS.items()
                    },
                },
            },
            self.ledger,
        )

        result = generate_performance_run_report(
            "11111111",
            ledger_path=self.ledger,
            reports_dir=self.reports,
        )
        report = json.loads(Path(result["json_path"]).read_text(encoding="utf-8"))
        self.assertIsNone(report["metrics"])
        self.assertIsNone(report["assessment"])
        self.assertTrue(report["ledger_verification"]["ok"])

    def test_untrusted_manifest_records_error_terminal_and_raises(self) -> None:
        with self.assertRaisesRegex(CoordinatorError, "evidence schema"):
            self.coordinator(FakeMcpClient(bad_manifest=True)).run(
                plan="smoke.jmx", run_id="abcdef12"
            )

        events = self.events()
        self.assertEqual(len(events), 3)
        self.assertEqual(events[-1]["event_type"], "performance.run.error")
        self.assertEqual(events[-1]["error"]["type"], "CoordinatorError")

    def test_remote_errors_cannot_write_property_values_to_ledger(self) -> None:
        with self.assertRaises(CoordinatorError):
            self.coordinator(SecretEchoingFailureClient()).run(
                plan="smoke.jmx",
                run_id="abcdef12",
                properties={"token": "do-not-persist"},
            )

        serialized = self.ledger.read_text(encoding="utf-8")
        self.assertNotIn("do-not-persist", serialized)
        self.assertIn("<redacted>", serialized)

    def test_tampering_breaks_ledger_verification(self) -> None:
        self.coordinator(FakeMcpClient()).run(
            plan="smoke.jmx", run_id="abcdef12"
        )
        events = self.events()
        events[0]["plan"] = "tampered.jmx"
        self.ledger.write_text(
            "\n".join(json.dumps(event) for event in events) + "\n", encoding="utf-8"
        )

        errors = verify_performance_run_ledger(self.ledger)
        self.assertTrue(any("event_hash does not match" in error for error in errors))

    def test_request_validation_happens_before_ledger_write(self) -> None:
        with self.assertRaisesRegex(ValueError, "simple .jmx"):
            self.coordinator(FakeMcpClient()).run(
                plan="../escape.jmx", run_id="abcdef12"
            )
        self.assertFalse(self.ledger.exists())

    def test_streamable_http_response_decoder_accepts_sse_and_rejects_noise(self) -> None:
        decoded = JMeterMcpClient._decode_response(
            'event: message\ndata: {"jsonrpc":"2.0","id":1,"result":{}}\n\n'
        )
        self.assertEqual(decoded["id"], 1)
        with self.assertRaises(McpClientError):
            JMeterMcpClient._decode_response("not-json")


if __name__ == "__main__":
    unittest.main()
