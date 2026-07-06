from pathlib import Path
from datetime import datetime, timezone
import json
from collections import Counter

LEDGER_PATH = Path("persona_ledger/persona_test_events.jsonl")
TOKEN_REPORT_PATH = Path("reports/token_burn_report.md")
PERSONA_REPORT_PATH = Path("reports/persona_test_report.md")
OUTPUT_PATH = Path("reports/ideation_engine_report.md")


def load_jsonl(path: Path):
    events = []
    if not path.exists():
        print(f"Warning: {path} not found.")
        return events

    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue

    return events


def nested_get(data, keys, default=None):
    current = data
    for key in keys:
        if isinstance(current, dict):
            current = current.get(key, default)
        else:
            return default
    return current


def load_report_excerpt(path: Path, max_chars=1200):
    if not path.exists():
        return "Report not found."
    text = path.read_text(encoding="utf-8")
    return text[:max_chars].strip()


def analyze_ledger(events):
    persona_counts = Counter()
    scenario_counts = Counter()

    total_violations = 0
    token_events = 0
    drift_values = []
    coherence_values = []

    for event in events:
        persona_name = nested_get(event, ["persona", "persona_name"], "Unknown")
        scenario_id = (
            nested_get(event, ["scenario", "scenario_id"], None)
            or event.get("scenario_id")
            or "Unknown"
        )

        persona_counts[persona_name] += 1
        scenario_counts[scenario_id] += 1

        assessment = event.get("assessment", {})

        violations = assessment.get("violations", []) or []
        total_violations += len(violations)

        if assessment.get("token_economics"):
            token_events += 1

        drift = assessment.get("drift_risk")
        coherence = assessment.get("persona_coherence")

        if isinstance(drift, (int, float)):
            drift_values.append(drift)
        if isinstance(coherence, (int, float)):
            coherence_values.append(coherence)

    avg_drift = sum(drift_values) / len(drift_values) if drift_values else None
    avg_coherence = sum(coherence_values) / len(coherence_values) if coherence_values else None

    return {
        "total_events": len(events),
        "persona_counts": persona_counts,
        "scenario_counts": scenario_counts,
        "total_violations": total_violations,
        "token_events": token_events,
        "avg_drift": avg_drift,
        "avg_coherence": avg_coherence,
    }


def build_idea_candidates(analysis):
    total_events = analysis["total_events"]
    total_violations = analysis["total_violations"]
    token_events = analysis["token_events"]

    return [
        {
            "name": "Behavioral Version Control",
            "description": (
                "A governance mechanism for tracking AI persona identity, behavioral changes, "
                "assessment outcomes, violations, and drift across time."
            ),
            "source_evidence": (
                f"The Ledger currently contains {total_events} persona test events and "
                f"{total_violations} detected violations, creating the basis for tracking behavioral state over time."
            ),
            "related_concepts": [
                "Persona Ledger",
                "Assessor",
                "persona persistence",
                "drift monitoring",
                "governance history",
            ],
            "reasoning_path": (
                "If persona behavior can be logged, scored, and assessed over time, then persona identity "
                "can be versioned similarly to how software systems track source changes."
            ),
            "significance": (
                "Provides a foundation for enterprise auditability, approval history, drift detection, "
                "and governed AI identity management."
            ),
            "assessor_review": "High coherence; strong fit with existing Ledger and Assessor architecture.",
            "recommended_action": "Promote to concept record and define a formal persona_version_event schema.",
        },
        {
            "name": "Persona-Governed AI Testing",
            "description": (
                "A testing architecture where specialized testing personas coordinate API testing, "
                "web automation, AI output evaluation, and evidence capture."
            ),
            "source_evidence": (
                "The existing Persona Test Harness Report demonstrates persona-level testing, "
                "coherence scoring, violation tracking, and drift-risk monitoring."
            ),
            "related_concepts": [
                "test harness",
                "AI testing governance",
                "Selenium MCP",
                "API testing",
                "Assessor",
            ],
            "reasoning_path": (
                "If the Persona Engineering layer can test and assess persona behavior, the same governance pattern "
                "can be extended to broader AI testing domains."
            ),
            "significance": (
                "Bridges conventional QA automation with AI governance, enabling accountable testing across tools and workflows."
            ),
            "assessor_review": "Strong technical and commercial relevance; should be developed incrementally.",
            "recommended_action": "Add test_domain fields and integrate API/web automation events into the Ledger.",
        },
        {
            "name": "Token Governance Monitor",
            "description": (
                "A monitoring unit for tracking token burn and estimating avoidable interaction overhead "
                "under governed versus theoretical ungoverned conditions."
            ),
            "source_evidence": (
                f"The Ledger contains {token_events} events with token economics. Existing token burn reporting "
                "already compares governed token estimates to a theoretical baseline."
            ),
            "related_concepts": [
                "token burn",
                "cost governance",
                "operational telemetry",
                "interaction efficiency",
                "Ledger analytics",
            ],
            "reasoning_path": (
                "If token usage can be attached to persona-governed interactions, then cost can become a governable "
                "interaction-level metric."
            ),
            "significance": (
                "Supports management visibility into AI cost, waste, usage patterns, and the operational value of governance."
            ),
            "assessor_review": "Promising but currently limited by estimated token metrics; provider usage metrics should be added.",
            "recommended_action": "Replace character-count approximations with actual provider token usage where available.",
        },
        {
            "name": "Concepts Pool",
            "description": (
                "A semantic memory repository that stores concepts extracted from Ledger history, Assessor outputs, "
                "reports, and ideation results."
            ),
            "source_evidence": (
                "Repeated concepts across the Ledger and reports include Assessor, Ledger, drift, testing, "
                "token governance, persona persistence, and Synthetic Cognition."
            ),
            "related_concepts": [
                "vector DB",
                "Synthetic Cognition",
                "semantic memory",
                "concept formation",
                "ideation",
            ],
            "reasoning_path": (
                "If Ledger records accumulate repeated concepts, those concepts can be embedded, retrieved, clustered, "
                "and recombined as source material for future synthesis."
            ),
            "significance": (
                "Creates the foundation for synthetic cognition: memory that is not merely stored, but semantically reusable."
            ),
            "assessor_review": "High strategic importance; requires vector DB integration to mature.",
            "recommended_action": "Connect promoted concept records to Chroma or another vector database.",
        },
        {
            "name": "Centaur Assessor",
            "description": (
                "A future assessment layer that evaluates the human-AI collaboration itself rather than only the AI persona."
            ),
            "source_evidence": (
                "The Persona Engineering roadmap includes AI Assessor, Human Assessor, and Centaur Assessor concepts."
            ),
            "related_concepts": [
                "Centaur Gestalt",
                "Human Assessor",
                "AI Assessor",
                "relationship governance",
                "collaborative intelligence",
            ],
            "reasoning_path": (
                "If the AI persona can be assessed and the human can revise the frame, then the next evaluable object "
                "is the human-AI coupling itself."
            ),
            "significance": (
                "Extends Persona Engineering from AI identity governance into human-AI system governance."
            ),
            "assessor_review": "Conceptually strong but still theoretical; suitable for research-track development.",
            "recommended_action": "Define first-pass metrics for evaluating human-AI collaboration quality.",
        },
    ]


def generate_report():
    events = load_jsonl(LEDGER_PATH)
    analysis = analyze_ledger(events)
    ideas = build_idea_candidates(analysis)

    persona_report_excerpt = load_report_excerpt(PERSONA_REPORT_PATH)
    token_report_excerpt = load_report_excerpt(TOKEN_REPORT_PATH)

    lines = []

    lines.append("# Ideation Engine Report")
    lines.append("")
    lines.append(f"Generated: `{datetime.now(timezone.utc).isoformat()}`")
    lines.append("")
    lines.append("## Synthesis Query")
    lines.append("")
    lines.append(
        "Review the existing Persona Ledger, including persona test events, Assessor evaluations, "
        "violation records, drift-risk scores, and token-governance data. Synthesize 3 to 5 high-value "
        "idea candidates and trace each idea back to Ledger evidence."
    )
    lines.append("")

    lines.append("## Source Records Examined")
    lines.append("")
    lines.append(f"- Ledger path: `{LEDGER_PATH}`")
    lines.append(f"- Ledger events loaded: **{analysis['total_events']}**")
    lines.append(f"- Personas observed: **{len(analysis['persona_counts'])}**")
    lines.append(f"- Scenarios observed: **{len(analysis['scenario_counts'])}**")
    lines.append(f"- Parsed violations: **{analysis['total_violations']}**")
    lines.append(f"- Events with token economics: **{analysis['token_events']}**")
    if analysis["avg_coherence"] is not None:
        lines.append(f"- Average parsed persona coherence: **{analysis['avg_coherence']:.3f}**")
    if analysis["avg_drift"] is not None:
        lines.append(f"- Average parsed drift risk: **{analysis['avg_drift']:.3f}**")
    lines.append("")

    lines.append("## Concepts Pool Snapshot")
    lines.append("")
    concepts = [
        "Persona Ledger",
        "Assessor",
        "Persona persistence",
        "Persona coherence",
        "Drift monitoring",
        "Violation tracking",
        "Token governance",
        "Behavioral version control",
        "AI testing governance",
        "Synthetic Cognition",
        "Centaur Gestalt",
    ]
    for concept in concepts:
        lines.append(f"- {concept}")
    lines.append("")

    lines.append("## Generated Idea Candidates")
    lines.append("")
    for index, idea in enumerate(ideas, start=1):
        lines.append(f"### {index}. {idea['name']}")
        lines.append("")
        lines.append(f"**Description:** {idea['description']}")
        lines.append("")
        lines.append(f"**Source evidence:** {idea['source_evidence']}")
        lines.append("")
        lines.append(f"**Related concepts:** {', '.join(idea['related_concepts'])}")
        lines.append("")
        lines.append(f"**Reasoning path:** {idea['reasoning_path']}")
        lines.append("")
        lines.append(f"**Technical or commercial significance:** {idea['significance']}")
        lines.append("")
        lines.append(f"**Assessor-style review:** {idea['assessor_review']}")
        lines.append("")
        lines.append(f"**Recommended next action:** {idea['recommended_action']}")
        lines.append("")

    lines.append("## Idea Lineage Summary")
    lines.append("")
    lines.append("| Idea | Primary Sources | Recommended Status |")
    lines.append("|---|---|---|")
    lines.append("| Behavioral Version Control | Persona test events, Assessor metrics, Ledger history | Promote to concept record |")
    lines.append("| Persona-Governed AI Testing | Persona test harness report, testing architecture | Develop |")
    lines.append("| Token Governance Monitor | Token burn report, token economics fields | Develop |")
    lines.append("| Concepts Pool | Ledger history, repeated concepts, vector DB plan | Build next |")
    lines.append("| Centaur Assessor | Assessor architecture, Centaur Gestalt theory | Research track |")
    lines.append("")

    lines.append("## Existing Report Excerpts")
    lines.append("")
    lines.append("### Persona Test Report Excerpt")
    lines.append("")
    lines.append("```markdown")
    lines.append(persona_report_excerpt)
    lines.append("```")
    lines.append("")
    lines.append("### Token Burn Report Excerpt")
    lines.append("")
    lines.append("```markdown")
    lines.append(token_report_excerpt)
    lines.append("```")
    lines.append("")

    lines.append("## Notes")
    lines.append("")
    lines.append(
        "This is an early-stage Ideation Engine report. It demonstrates structured synthesis from Ledgered experience, "
        "not full Synthetic Cognition. Future versions should integrate vector retrieval, semantic clustering, idea scoring, "
        "Assessor review, and formal promotion into concept records."
    )
    lines.append("")

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {OUTPUT_PATH}")


if __name__ == "__main__":
    generate_report()