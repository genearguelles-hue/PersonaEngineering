"""Command-line entry point for PE-ordered, Ledger-recorded JMeter runs."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Sequence

from performance_test_harness.assessment import PerformancePolicy
from performance_test_harness.coordinator import PerformanceRunCoordinator
from performance_test_harness.ledger_writer import (
    DEFAULT_LEDGER_PATH,
    verify_performance_run_ledger,
)
from performance_test_harness.mcp_client import JMeterMcpClient
from performance_test_harness.reporting import (
    DEFAULT_REPORTS_DIR,
    generate_performance_run_report,
)


def _properties(values: Sequence[str]) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for item in values:
        if "=" not in item:
            raise argparse.ArgumentTypeError("properties must use NAME=VALUE")
        name, value = item.split("=", 1)
        if name in parsed:
            raise argparse.ArgumentTypeError(f"duplicate property: {name}")
        parsed[name] = value
    return parsed


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m performance_test_harness")
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser("run", help="Order JMeter through MCP and record Ledger events")
    run.add_argument(
        "--mcp-url",
        default=os.environ.get("JMETER_MCP_URL", "http://127.0.0.1:8000/mcp/"),
    )
    run.add_argument("--plan", required=True)
    run.add_argument("--run-id")
    run.add_argument("--property", action="append", default=[])
    run.add_argument("--ledger", type=Path, default=DEFAULT_LEDGER_PATH)
    run.add_argument("--timeout-seconds", type=float, default=660.0)
    run.add_argument(
        "--initiator", default="persona-engineering.performance-test-harness"
    )
    run.add_argument("--reports-dir", type=Path, default=DEFAULT_REPORTS_DIR)
    run.add_argument("--policy-id", default="pe.jmeter.smoke.baseline")
    run.add_argument("--min-sample-count", type=int, default=1)
    run.add_argument("--max-error-rate", type=float, default=0.0)
    run.add_argument("--max-p95-elapsed-ms", type=float, default=1000.0)
    run.add_argument("--min-throughput-per-second", type=float, default=0.1)
    verify = commands.add_parser("verify-ledger", help="Validate the Ledger hash chain")
    verify.add_argument("--ledger", type=Path, default=DEFAULT_LEDGER_PATH)
    report = commands.add_parser(
        "report", help="Regenerate JSON and Markdown reports from the verified Ledger"
    )
    report.add_argument("--run-id", required=True)
    report.add_argument("--ledger", type=Path, default=DEFAULT_LEDGER_PATH)
    report.add_argument("--reports-dir", type=Path, default=DEFAULT_REPORTS_DIR)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "verify-ledger":
        errors = verify_performance_run_ledger(args.ledger)
        print(json.dumps({"ok": not errors, "errors": errors}, sort_keys=True))
        return 0 if not errors else 1
    if args.command == "report":
        try:
            result = generate_performance_run_report(
                args.run_id,
                ledger_path=args.ledger,
                reports_dir=args.reports_dir,
            )
            print(json.dumps(result, sort_keys=True))
            return 0
        except Exception as exc:
            print(
                json.dumps(
                    {
                        "ok": False,
                        "error": {
                            "type": type(exc).__name__,
                            "message": str(exc),
                        },
                    },
                    sort_keys=True,
                )
            )
            return 2

    try:
        properties = _properties(args.property)
        policy = PerformancePolicy(
            policy_id=args.policy_id,
            min_sample_count=args.min_sample_count,
            max_error_rate=args.max_error_rate,
            max_p95_elapsed_ms=args.max_p95_elapsed_ms,
            min_throughput_per_second=args.min_throughput_per_second,
        )
        with JMeterMcpClient(args.mcp_url, args.timeout_seconds) as client:
            result = PerformanceRunCoordinator(
                client,
                ledger_path=args.ledger,
                initiator=args.initiator,
                policy=policy,
                reports_dir=args.reports_dir,
            ).run(plan=args.plan, run_id=args.run_id, properties=properties)
        print(json.dumps(result, sort_keys=True))
        return 0 if result["ok"] else 1
    except Exception as exc:
        print(
            json.dumps(
                {
                    "ok": False,
                    "error": {"type": type(exc).__name__, "message": str(exc)},
                },
                sort_keys=True,
            )
        )
        return 2
