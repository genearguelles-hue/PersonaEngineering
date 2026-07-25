#!/usr/bin/env python3

import argparse
import json
import subprocess
import uuid
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
SELENIUM_MODULE = REPO_ROOT / "test-automation-java" / "selenium-tests"
LEDGER_PATH = REPO_ROOT / "persona_ledger" / "selenium_test_runs.jsonl"
REPORT_DIR = REPO_ROOT / "reports" / "selenium"
SUREFIRE_DIR = SELENIUM_MODULE / "target" / "surefire-reports"
SCREENSHOT_DIR = SELENIUM_MODULE / "target" / "screenshots"


def now_utc():
    return datetime.now(timezone.utc).isoformat()


def run_maven_tests(headless: bool, run_id: str):
    command = ["mvn", "clean", "test", f"-Dheadless={str(headless).lower()}"]

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    log_path = REPORT_DIR / f"selenium_run_{run_id}.log"

    started_at = now_utc()

    with log_path.open("w", encoding="utf-8") as log_file:
        log_file.write(f"Command: {' '.join(command)}\n")
        log_file.write(f"Started: {started_at}\n\n")
        log_file.flush()

        process = subprocess.Popen(
            command,
            cwd=SELENIUM_MODULE,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            bufsize=1,
        )

        for line in process.stdout:
            print(line, end="")
            log_file.write(line)

        process.wait()

    ended_at = now_utc()

    return {
        "command": " ".join(command),
        "exit_code": process.returncode,
        "stdout_log": str(log_path.relative_to(REPO_ROOT)),
        "started_at": started_at,
        "ended_at": ended_at,
    }

    ended_at = now_utc()

    return {
        "command": " ".join(command),
        "exit_code": process.returncode,
        "stdout": process.stdout,
        "started_at": started_at,
        "ended_at": ended_at,
    }


def parse_surefire_results():
    summary = {
        "tests": 0,
        "failures": 0,
        "errors": 0,
        "skipped": 0,
        "testcases": [],
    }

    if not SUREFIRE_DIR.exists():
        return summary

    for xml_file in SUREFIRE_DIR.glob("TEST-*.xml"):
        tree = ET.parse(xml_file)
        root = tree.getroot()

        summary["tests"] += int(root.attrib.get("tests", 0))
        summary["failures"] += int(root.attrib.get("failures", 0))
        summary["errors"] += int(root.attrib.get("errors", 0))
        summary["skipped"] += int(root.attrib.get("skipped", 0))

        for testcase in root.findall("testcase"):
            name = testcase.attrib.get("name")
            classname = testcase.attrib.get("classname")
            time_seconds = testcase.attrib.get("time")

            status = "passed"
            details = None

            failure = testcase.find("failure")
            error = testcase.find("error")
            skipped = testcase.find("skipped")

            if failure is not None:
                status = "failed"
                details = failure.attrib.get("message")
            elif error is not None:
                status = "error"
                details = error.attrib.get("message")
            elif skipped is not None:
                status = "skipped"
                details = "skipped"

            summary["testcases"].append({
                "classname": classname,
                "name": name,
                "status": status,
                "time_seconds": time_seconds,
                "details": details,
            })

    return summary


def collect_failure_screenshots():
    if not SCREENSHOT_DIR.exists():
        return []

    screenshots = []

    for screenshot in sorted(SCREENSHOT_DIR.glob("*FAILED*.png")):
        screenshots.append(str(screenshot.relative_to(REPO_ROOT)))

    return screenshots


def determine_status(exit_code, surefire_summary):
    if exit_code != 0:
        return "failed"

    if surefire_summary["failures"] > 0 or surefire_summary["errors"] > 0:
        return "failed"

    return "passed"


def build_ledger_event(run_id, maven_result, surefire_summary, screenshots, status):
    return {
        "event_type": "selenium_test_run",
        "schema_version": "pe.selenium.run.v1",
        "run_id": run_id,
        "timestamp_utc": now_utc(),
        "persona_context": {
            "domain": "Persona-Engineered AI Test Automation Framework",
            "execution_layer": "java_selenium",
            "runner": "selenium_pe_runner.py",
            "test_framework": "JUnit 5",
            "build_tool": "Maven",
        },
        "execution": {
            "command": maven_result["command"],
            "module_path": str(SELENIUM_MODULE.relative_to(REPO_ROOT)),
            "stdout_log": maven_result["stdout_log"],
            "started_at": maven_result["started_at"],
            "ended_at": maven_result["ended_at"],
            "exit_code": maven_result["exit_code"],
        },
        "result": {
            "status": status,
            "tests": surefire_summary["tests"],
            "failures": surefire_summary["failures"],
            "errors": surefire_summary["errors"],
            "skipped": surefire_summary["skipped"],
            "testcases": surefire_summary["testcases"],
        },
        "evidence": {
            "surefire_reports": str(SUREFIRE_DIR.relative_to(REPO_ROOT)),
            "failure_screenshots": screenshots,
        },
    }


def append_ledger_event(event):
    LEDGER_PATH.parent.mkdir(parents=True, exist_ok=True)

    with LEDGER_PATH.open("a", encoding="utf-8") as ledger:
        ledger.write(json.dumps(event, ensure_ascii=False) + "\n")


def write_markdown_report(event):
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    report_path = REPORT_DIR / f"selenium_run_{event['run_id']}.md"

    lines = [
        f"# Selenium PE Run Report",
        "",
        f"Run ID: `{event['run_id']}`",
        "",
        f"Status: **{event['result']['status'].upper()}**",
        "",
        "## Execution",
        "",
        f"- Command: `{event['execution']['command']}`",
        f"- Maven log: `{event['execution']['stdout_log']}`",
        f"- Module: `{event['execution']['module_path']}`",
        f"- Started: `{event['execution']['started_at']}`",
        f"- Ended: `{event['execution']['ended_at']}`",
        f"- Exit code: `{event['execution']['exit_code']}`",
        "",
        "## Result Summary",
        "",
        f"- Tests: `{event['result']['tests']}`",
        f"- Failures: `{event['result']['failures']}`",
        f"- Errors: `{event['result']['errors']}`",
        f"- Skipped: `{event['result']['skipped']}`",
        "",
        "## Test Cases",
        "",
    ]

    for testcase in event["result"]["testcases"]:
        lines.append(
            f"- `{testcase['classname']}#{testcase['name']}` — **{testcase['status']}**"
        )
        if testcase.get("details"):
            lines.append(f"  - Details: {testcase['details']}")

    lines.extend([
        "",
        "## Evidence",
        "",
        f"- Surefire reports: `{event['evidence']['surefire_reports']}`",
    ])

    screenshots = event["evidence"]["failure_screenshots"]

    if screenshots:
        lines.append("- Failure screenshots:")
        for screenshot in screenshots:
            lines.append(f"  - `{screenshot}`")
    else:
        lines.append("- Failure screenshots: none")

    report_path.write_text("\n".join(lines), encoding="utf-8")

    return report_path


def main():
    parser = argparse.ArgumentParser(
        description="Run Selenium smoke tests and record Persona Engineering ledger evidence."
    )

    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run browser tests in headless mode.",
    )

    args = parser.parse_args()

    run_id = uuid.uuid4().hex[:12]

    print(f"Starting Selenium PE run: {run_id}")

    maven_result = run_maven_tests(headless=args.headless, run_id=run_id)
    surefire_summary = parse_surefire_results()
    screenshots = collect_failure_screenshots()
    status = determine_status(maven_result["exit_code"], surefire_summary)

    event = build_ledger_event(
        run_id=run_id,
        maven_result=maven_result,
        surefire_summary=surefire_summary,
        screenshots=screenshots,
        status=status,
    )

    append_ledger_event(event)
    report_path = write_markdown_report(event)

    print("")
    print(f"Run ID: {run_id}")
    print(f"Status: {status}")
    print(f"Ledger: {LEDGER_PATH}")
    print(f"Report: {report_path}")

    raise SystemExit(maven_result["exit_code"])


if __name__ == "__main__":
    main()