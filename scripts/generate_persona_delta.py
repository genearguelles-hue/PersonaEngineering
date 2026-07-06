#!/usr/bin/env python3
"""
Generate a proposed Persona Delta from recent Ledger experience.

This script does NOT modify the persona.
It reads Ledger events, extracts experience-derived signals, and writes
an auditable delta proposal.

Formula:
Persona(t+1) = Persona(t) + Δ(Experience)
"""

import argparse
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4


DEFAULT_LEDGER = "persona_ledger/persona_test_events.jsonl"
DEFAULT_PERSONA = "personas/the_structured_companion/persona.json"
DEFAULT_OUTPUT_DIR = "persona_memory/deltas"


STOPWORDS = {
    "the", "and", "for", "with", "that", "this", "from", "into", "have",
    "has", "are", "was", "were", "you", "your", "our", "can", "will",
    "not", "but", "they", "their", "what", "when", "where", "how",
    "persona", "engineering", "user", "response", "output", "input"
}

def slugify(value: str) -> str:
    return (
        value.strip()
        .lower()
        .replace(" ", "_")
        .replace("-", "_")
    )

IMPORTANT_TERMS = [
    "synthetic cognition",
    "synthetic learning",
    "persona delta",
    "delta engine",
    "ledger",
    "vector database",
    "concept formation",
    "ideation module",
    "engram",
    "axiom",
    "primitive",
    "persona state",
    "token burn",
    "governance",
    "assessor",
    "drift",
    "experience",
    "learning",
]


def load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def load_jsonl(path: Path, limit: int | None = None) -> list[dict]:
    if not path.exists():
        raise FileNotFoundError(f"Ledger not found: {path}")

    rows = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue

    if limit:
        rows = rows[-limit:]

    return rows


def flatten_text(obj) -> str:
    if obj is None:
        return ""
    if isinstance(obj, str):
        return obj
    if isinstance(obj, dict):
        return " ".join(flatten_text(v) for v in obj.values())
    if isinstance(obj, list):
        return " ".join(flatten_text(v) for v in obj)
    return str(obj)


def extract_keywords(text: str, max_terms: int = 25) -> list[str]:
    words = re.findall(r"[a-zA-Z][a-zA-Z\-]{3,}", text.lower())
    words = [w for w in words if w not in STOPWORDS]
    counts = Counter(words)
    return [term for term, _ in counts.most_common(max_terms)]


def detect_important_concepts(text: str) -> list[str]:
    text_lower = text.lower()
    found = []
    for term in IMPORTANT_TERMS:
        if term in text_lower:
            found.append(term)
    return sorted(set(found))


def infer_patterns(events: list[dict], text: str) -> list[str]:
    patterns = []

    if "roadmap" in text.lower() or "next step" in text.lower():
        patterns.append("User prefers theory to be connected to concrete implementation steps.")

    if "token burn" in text.lower():
        patterns.append("User values measurable efficiency and cost-reduction evidence.")

    if "ledger" in text.lower():
        patterns.append("User treats Ledger records as the source of experiential memory.")

    if "synthetic cognition" in text.lower() or "synthetic learning" in text.lower():
        patterns.append("User is focused on proving learning and cognition at the Persona Engineering layer.")

    if "assessor" in text.lower() or "governance" in text.lower():
        patterns.append("User prefers persona evolution to remain governed, auditable, and constrained.")

    if len(events) >= 10:
        patterns.append("Repeated interaction history is sufficient to propose a bounded persona delta.")

    return sorted(set(patterns))


def infer_failure_patterns(text: str) -> list[str]:
    failures = []

    if "missing" in text.lower():
        failures.append("Current architecture may record experience without yet applying experience-derived persona updates.")

    if "drift" in text.lower():
        failures.append("Persona evolution requires drift detection to distinguish valid adaptation from identity erosion.")

    return sorted(set(failures))


def build_delta(persona: dict, events: list[dict]) -> dict:
    text = flatten_text(events)

    concepts = detect_important_concepts(text)
    keywords = extract_keywords(text)
    reinforced_patterns = infer_patterns(events, text)
    failure_patterns = infer_failure_patterns(text)

    persona_block = persona.get("persona", {})
    metadata_block = persona.get("metadata", {})
    identity_block = persona.get("identity", {})

    raw_persona_id = (
        persona.get("persona_id")
        or metadata_block.get("persona_id")
        or identity_block.get("persona_id")
        or persona_block.get("persona_id")
        or None
    )

    persona_name = (
        persona.get("name")
        or persona.get("persona_name")
        or metadata_block.get("name")
        or metadata_block.get("persona_name")
        or identity_block.get("name")
        or persona_block.get("name")
        or persona_block.get("persona_name")
        or "Unknown Persona"
    )

    persona_id = raw_persona_id or slugify(persona_name)

    now = datetime.now(timezone.utc).isoformat()

    return {
        "event_type": "persona_delta_proposal",
        "schema_version": "0.1",
        "delta_id": str(uuid4()),
        "timestamp": now,
        "formula": "Persona(t+1) = Persona(t) + Δ(Experience)",
        "persona": {
            "persona_id": persona_id,
            "persona_name": persona_name,
            "source_persona_file": DEFAULT_PERSONA,
        },
        "source": {
            "ledger_event_count": len(events),
            "source_type": "ledger_experience",
        },
        "delta_type": "experience_derived_update",
        "proposed_updates": {
            "known_concepts": concepts,
            "keywords": keywords,
            "reinforced_interaction_patterns": reinforced_patterns,
            "observed_failure_patterns": failure_patterns,
            "open_questions": [
                "Which proposed concepts should become durable persona engrams?",
                "Which interaction patterns are strong enough to influence future persona behavior?",
                "What assessor criteria should approve or reject this delta?"
            ],
        },
        "protected_fields": [
            "persona_id",
            "core_mission",
            "persona_axioms",
            "persona_primitives",
            "safety_boundaries",
        ],
        "governance": {
            "requires_assessor_approval": True,
            "auto_apply": False,
            "reason": "This is a proposed delta only. Persona identity should not change without review.",
        },
    }


def main():
    parser = argparse.ArgumentParser(
        description="Generate an auditable persona delta from Ledger experience."
    )

    parser.add_argument("--ledger", default=DEFAULT_LEDGER)
    parser.add_argument("--persona", default=DEFAULT_PERSONA)
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--limit", type=int, default=50)

    args = parser.parse_args()

    ledger_path = Path(args.ledger)
    persona_path = Path(args.persona)
    output_dir = Path(args.output_dir)

    persona = load_json(persona_path)
    events = load_jsonl(ledger_path, limit=args.limit)

    delta = build_delta(persona, events)

    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    persona_id = delta["persona"]["persona_id"]
    output_path = output_dir / f"{persona_id}_delta_{timestamp}.json"

    with output_path.open("w", encoding="utf-8") as f:
        json.dump(delta, f, indent=2, ensure_ascii=False)

    print(f"Persona delta proposal generated:")
    print(output_path)


if __name__ == "__main__":
    main()