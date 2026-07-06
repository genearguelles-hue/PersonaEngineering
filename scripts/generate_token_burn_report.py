#!/usr/bin/env python3

import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List


LEDGER_PATH = Path("persona_ledger/persona_test_events.jsonl")
REPORT_PATH = Path("reports/token_burn_report.md")


def load_events(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []

    events = []

    with path.open("r", encoding="utf-8") as file:
        for line in file:
            line = line.strip()
            if not line:
                continue

            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                continue

    return events


def get_token_economics(event: Dict[str, Any]) -> Dict[str, Any]:
    return event.get("assessment", {}).get("token_economics", {}) or {}


def safe_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def summarize_events(events: List[Dict[str, Any]]) -> Dict[str, Any]:
    summary = {
        "event_count": 0,
        "events_with_token_data": 0,
        "governed_tokens": 0,
        "baseline_tokens": 0,
        "token_savings": 0,
        "by_persona": defaultdict(lambda: {
            "event_count": 0,
            "events_with_token_data": 0,
            "governed_tokens": 0,
            "baseline_tokens": 0,
            "token_savings": 0,
        }),
        "by_scenario": defaultdict(lambda: {
            "event_count": 0,
            "events_with_token_data": 0,
            "governed_tokens": 0,
            "baseline_tokens": 0,
            "token_savings": 0,
        }),
        "high_burn_events": []
    }

    for event in events:
        summary["event_count"] += 1

        persona = event.get("persona", {})
        persona_id = persona.get("persona_id", "unknown")
        persona_name = persona.get("persona_name", persona_id)

        metadata = event.get("test_metadata", {})
        scenario_id = metadata.get("scenario_id", "unknown")

        token_data = get_token_economics(event)

        governed = safe_int(token_data.get("total_token_estimate"))
        baseline = safe_int(token_data.get("baseline_token_estimate"))
        savings = safe_int(token_data.get("estimated_token_savings"))

        persona_key = f"{persona_name} ({persona_id})"
        scenario_key = scenario_id

        summary["by_persona"][persona_key]["event_count"] += 1
        summary["by_scenario"][scenario_key]["event_count"] += 1

        if token_data:
            summary["events_with_token_data"] += 1
            summary["governed_tokens"] += governed
            summary["baseline_tokens"] += baseline
            summary["token_savings"] += savings

            summary["by_persona"][persona_key]["events_with_token_data"] += 1
            summary["by_persona"][persona_key]["governed_tokens"] += governed
            summary["by_persona"][persona_key]["baseline_tokens"] += baseline
            summary["by_persona"][persona_key]["token_savings"] += savings

            summary["by_scenario"][scenario_key]["events_with_token_data"] += 1
            summary["by_scenario"][scenario_key]["governed_tokens"] += governed
            summary["by_scenario"][scenario_key]["baseline_tokens"] += baseline
            summary["by_scenario"][scenario_key]["token_savings"] += savings

            summary["high_burn_events"].append({
                "event_id": event.get("event_id", "unknown"),
                "timestamp": event.get("timestamp", "unknown"),
                "persona": persona_key,
                "scenario_id": scenario_id,
                "governed_tokens": governed,
                "baseline_tokens": baseline,
                "token_savings": savings,
                "user_input_preview": (
                    event.get("interaction", {})
                    .get("user_input", "")
                    .replace("\n", " ")[:160]
                )
            })

    summary["high_burn_events"].sort(
        key=lambda item: item["governed_tokens"],
        reverse=True
    )

    return summary


def savings_ratio(token_savings: int, baseline_tokens: int) -> float:
    if baseline_tokens <= 0:
        return 0.0
    return round(token_savings / baseline_tokens, 3)


def render_rollup_table(title: str, rows: Dict[str, Dict[str, int]]) -> List[str]:
    lines = [
        f"## {title}",
        "",
        "| Group | Events | With Token Data | Governed Tokens | Baseline Tokens | Estimated Savings | Savings Ratio |",
        "|---|---:|---:|---:|---:|---:|---:|"
    ]

    for group, data in sorted(rows.items()):
        ratio = savings_ratio(data["token_savings"], data["baseline_tokens"])
        lines.append(
            f"| {group} | "
            f"{data['event_count']} | "
            f"{data['events_with_token_data']} | "
            f"{data['governed_tokens']} | "
            f"{data['baseline_tokens']} | "
            f"{data['token_savings']} | "
            f"{ratio:.3f} |"
        )

    lines.append("")
    return lines


def generate_report(events: List[Dict[str, Any]]) -> str:
    summary = summarize_events(events)

    overall_ratio = savings_ratio(
        summary["token_savings"],
        summary["baseline_tokens"]
    )

    lines = [
        "# Persona Token Burn Report",
        "",
        f"Generated: `{datetime.now(timezone.utc).isoformat()}`",
        "",
        "## Summary",
        "",
        f"- Total persona test events: **{summary['event_count']}**",
        f"- Events with token economics: **{summary['events_with_token_data']}**",
        f"- Estimated governed token burn: **{summary['governed_tokens']}**",
        f"- Estimated ungoverned baseline burn: **{summary['baseline_tokens']}**",
        f"- Estimated token savings: **{summary['token_savings']}**",
        f"- Estimated savings ratio: **{overall_ratio:.3f}**",
        "",
        "> Token economics are currently estimated using character-count approximation. "
        "Future versions can replace or supplement this with actual provider usage metrics.",
        ""
    ]

    lines.extend(render_rollup_table("Breakdown by Persona", summary["by_persona"]))
    lines.extend(render_rollup_table("Breakdown by Scenario", summary["by_scenario"]))

    lines.extend([
        "## Highest Governed Token Burn Events",
        "",
        "| Event ID | Timestamp | Persona | Scenario | Governed | Baseline | Savings | User Input Preview |",
        "|---|---|---|---|---:|---:|---:|---|"
    ])

    for event in summary["high_burn_events"][:10]:
        lines.append(
            f"| `{event['event_id']}` | "
            f"`{event['timestamp']}` | "
            f"{event['persona']} | "
            f"{event['scenario_id']} | "
            f"{event['governed_tokens']} | "
            f"{event['baseline_tokens']} | "
            f"{event['token_savings']} | "
            f"{event['user_input_preview']} |"
        )

    lines.extend([
        "",
        "## Notes",
        "",
        "This report reads from `persona_ledger/persona_test_events.jsonl` and aggregates "
        "`assessment.token_economics` fields created by the token assessor.",
        "",
        "Current baseline burn is theoretical and should be treated as an internal comparison model, "
        "not as billing-grade provider usage."
    ])

    return "\n".join(lines)


def main() -> None:
    events = load_events(LEDGER_PATH)
    report = generate_report(events)

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)

    with REPORT_PATH.open("w", encoding="utf-8") as file:
        file.write(report)

    print(f"✅ Token burn report generated: {REPORT_PATH.resolve()}")
    print(f"Events included: {len(events)}")


if __name__ == "__main__":
    main()