from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from performance_test_harness.coordinator import (
    CoordinatorError,
    PerformanceRunCoordinator,
)
from performance_test_harness.ledger_writer import verify_performance_run_ledger
from performance_test_harness.mcp_client import JMeterMcpClient, McpClientError


DIGESTS = {
    name: (str(index) * 64)
    for index, name in enumerate(
        ("test_plan", "jtl", "jmeter_log", "dashboard_index", "run_metadata"),
        start=1,
    )
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
    def __init__(self, *, status: str = "completed", bad_manifest: bool = False) -> None:
        self.status = status
        self.bad_manifest = bad_manifest
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
        raise AssertionError(f"unexpected tool: {name}")


class SecretEchoingFailureClient:
    def call_tool(self, name: str, arguments: dict) -> dict:
        raise RuntimeError(f"remote rejected {arguments['properties']['token']}")


class PerformanceRunLedgerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.ledger = Path(self.temporary.name) / "performance.jsonl"

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def events(self) -> list[dict]:
        return [
            json.loads(line)
            for line in self.ledger.read_text(encoding="utf-8").splitlines()
        ]

    def test_completed_run_records_ordered_hash_chained_evidence(self) -> None:
        client = FakeMcpClient()
        result = PerformanceRunCoordinator(client, ledger_path=self.ledger).run(
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
        self.assertEqual(verify_performance_run_ledger(self.ledger), [])

    def test_failed_executor_still_records_one_terminal_event(self) -> None:
        result = PerformanceRunCoordinator(
            FakeMcpClient(status="failed"), ledger_path=self.ledger
        ).run(plan="smoke.jmx", run_id="deadbeef")

        self.assertFalse(result["ok"])
        events = self.events()
        self.assertEqual(len(events), 3)
        self.assertEqual(events[-1]["event_type"], "performance.run.failed")
        self.assertEqual(events[-1]["status"], "failed")

    def test_untrusted_manifest_records_error_terminal_and_raises(self) -> None:
        with self.assertRaisesRegex(CoordinatorError, "evidence schema"):
            PerformanceRunCoordinator(
                FakeMcpClient(bad_manifest=True), ledger_path=self.ledger
            ).run(plan="smoke.jmx", run_id="abcdef12")

        events = self.events()
        self.assertEqual(len(events), 3)
        self.assertEqual(events[-1]["event_type"], "performance.run.error")
        self.assertEqual(events[-1]["error"]["type"], "CoordinatorError")

    def test_remote_errors_cannot_write_property_values_to_ledger(self) -> None:
        with self.assertRaises(CoordinatorError):
            PerformanceRunCoordinator(
                SecretEchoingFailureClient(), ledger_path=self.ledger
            ).run(
                plan="smoke.jmx",
                run_id="abcdef12",
                properties={"token": "do-not-persist"},
            )

        serialized = self.ledger.read_text(encoding="utf-8")
        self.assertNotIn("do-not-persist", serialized)
        self.assertIn("<redacted>", serialized)

    def test_tampering_breaks_ledger_verification(self) -> None:
        PerformanceRunCoordinator(FakeMcpClient(), ledger_path=self.ledger).run(
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
            PerformanceRunCoordinator(FakeMcpClient(), ledger_path=self.ledger).run(
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
