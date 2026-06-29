import json
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any, Dict, List


SCORE_KEYS = [
    "axiom_compliance",
    "primitive_alignment",
    "persona_coherence",
    "response_quality",
    "drift_risk",
    "safety_risk",
]


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def load_ledger_events(ledger_path: Path) -> List[Dict[str, Any]]:
    if not ledger_path.exists():
        raise FileNotFoundError(f"Ledger file not found: {ledger_path}")

    events: List[Dict[str, Any]] = []

    with ledger_path.open("r", encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            line = line.strip()

            if not line:
                continue

            try:
                event = json.loads(line)
            except json.JSONDecodeError as exc:
                print(f"⚠️ Skipping invalid JSON on line {line_number}: {exc}")
                continue

            if event.get("event_type") == "persona_test_event":
                events.append(event)

    return events


def get_score(event: Dict[str, Any], score_key: str) -> float:
    value = (
        event
        .get("assessment", {})
        .get("scores", {})
        .get(score_key)
    )

    if isinstance(value, (int, float)):
        return float(value)

    return 0.0


def count_violations(events: List[Dict[str, Any]]) -> int:
    return sum(
        len(event.get("assessment", {}).get("violations", []))
        for event in events
    )


def average_scores(events: List[Dict[str, Any]]) -> Dict[str, float]:
    if not events:
        return {key: 0.0 for key in SCORE_KEYS}

    return {
        key: round(mean(get_score(event, key) for event in events), 3)
        for key in SCORE_KEYS
    }


def group_events_by_persona(events: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    grouped: Dict[str, List[Dict[str, Any]]] = {}

    for event in events:
        persona = event.get("persona", {})
        persona_name = persona.get("persona_name", "Unknown Persona")
        persona_id = persona.get("persona_id", "unknown_persona")
        label = f"{persona_name} ({persona_id})"

        grouped.setdefault(label, []).append(event)

    return grouped


def format_score(value: float) -> str:
    return f"{value:.3f}"


def generate_markdown_report(events: List[Dict[str, Any]]) -> str:
    generated_at = utc_now_iso()
    total_events = len(events)
    total_violations = count_violations(events)
    averages = average_scores(events)
    grouped = group_events_by_persona(events)

    lines: List[str] = []

    lines.append("# Persona Test Harness Report")
    lines.append("")
    lines.append(f"Generated: `{generated_at}`")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append(f"- Total persona test events: **{total_events}**")
    lines.append(f"- Total violations detected: **{total_violations}**")
    lines.append(f"- Personas observed: **{len(grouped)}**")
    lines.append("")
    lines.append("## Average Scores")
    lines.append("")
    lines.append("| Metric | Average |")
    lines.append("|---|---:|")

    for key in SCORE_KEYS:
        lines.append(f"| {key} | {format_score(averages[key])} |")

    lines.append("")
    lines.append("## Persona Breakdown")
    lines.append("")

    for persona_label, persona_events in grouped.items():
        persona_averages = average_scores(persona_events)
        persona_violations = count_violations(persona_events)

        lines.append(f"### {persona_label}")
        lines.append("")
        lines.append(f"- Events: **{len(persona_events)}**")
        lines.append(f"- Violations: **{persona_violations}**")
        lines.append("")
        lines.append("| Metric | Average |")
        lines.append("|---|---:|")

        for key in SCORE_KEYS:
            lines.append(f"| {key} | {format_score(persona_averages[key])} |")

        lines.append("")

    lines.append("## Recent Events")
    lines.append("")

    for event in events[-10:]:
        event_id = event.get("event_id", "unknown")
        timestamp = event.get("timestamp", "unknown")
        persona = event.get("persona", {})
        interaction = event.get("interaction", {})
        assessment = event.get("assessment", {})
        scores = assessment.get("scores", {})
        violations = assessment.get("violations", [])

        lines.append(f"### Event `{event_id}`")
        lines.append("")
        lines.append(f"- Timestamp: `{timestamp}`")
        lines.append(f"- Persona: **{persona.get('persona_name', 'Unknown')}**")
        lines.append(f"- User input: {interaction.get('user_input', '')}")
        lines.append(f"- Persona output: {interaction.get('persona_output', '')}")
        lines.append(f"- Persona coherence: `{scores.get('persona_coherence', 'n/a')}`")
        lines.append(f"- Drift risk: `{scores.get('drift_risk', 'n/a')}`")
        lines.append(f"- Violations: **{len(violations)}**")
        lines.append("")

    lines.append("## Notes")
    lines.append("")
    lines.append(
        "This report was generated from `persona_ledger/persona_test_events.jsonl`. "
        "Current scoring may include deterministic baseline assessments and manually captured events. "
        "Future versions will include semantic assessor evaluations, trend analysis, and governance recommendations."
    )
    lines.append("")

    return "\n".join(lines)


def write_report(report: str, report_path: Path) -> None:
    report_path.parent.mkdir(parents=True, exist_ok=True)

    with report_path.open("w", encoding="utf-8") as file:
        file.write(report)


def generate_report_from_ledger(
    ledger_path: Path,
    report_path: Path
) -> int:
    events = load_ledger_events(ledger_path)
    report = generate_markdown_report(events)
    write_report(report, report_path)

    return len(events)