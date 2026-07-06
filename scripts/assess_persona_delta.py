#!/usr/bin/env python3
"""
Assess a proposed Persona Delta before it can be applied.

This is the governance gate for:

Persona(t+1) = Persona(t) + Δ(Experience)

It reads a delta proposal, evaluates whether it is safe and bounded,
and writes an assessment report.

It does NOT apply the delta.
"""

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4


DEFAULT_OUTPUT_DIR = "persona_memory/delta_assessments"


PROTECTED_FIELDS = {
    "persona_id",
    "core_mission",
    "persona_axioms",
    "persona_primitives",
    "safety_boundaries",
}


def load_json(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def assess_known_concepts(concepts: list[str]) -> dict:
    approved = []
    rejected = []

    for concept in concepts:
        if not isinstance(concept, str):
            rejected.append({
                "value": concept,
                "reason": "Concept is not a string."
            })
            continue

        clean = concept.strip()

        if not clean:
            rejected.append({
                "value": concept,
                "reason": "Concept is empty."
            })
        elif len(clean) > 120:
            rejected.append({
                "value": concept,
                "reason": "Concept is too long to become a durable engram."
            })
        else:
            approved.append(clean)

    return {
        "approved": sorted(set(approved)),
        "rejected": rejected,
    }


def assess_patterns(patterns: list[str]) -> dict:
    approved = []
    rejected = []

    for pattern in patterns:
        if not isinstance(pattern, str):
            rejected.append({
                "value": pattern,
                "reason": "Pattern is not a string."
            })
            continue

        clean = pattern.strip()

        if not clean:
            rejected.append({
                "value": pattern,
                "reason": "Pattern is empty."
            })
        elif any(word in clean.lower() for word in ["always", "never", "must obey user"]):
            rejected.append({
                "value": pattern,
                "reason": "Pattern is too absolute and may weaken governance."
            })
        else:
            approved.append(clean)

    return {
        "approved": sorted(set(approved)),
        "rejected": rejected,
    }


def detect_protected_field_attempts(delta: dict) -> list[dict]:
    violations = []
    proposed_updates = delta.get("proposed_updates", {})

    for field in proposed_updates.keys():
        if field in PROTECTED_FIELDS:
            violations.append({
                "field": field,
                "reason": "Delta attempts to modify a protected persona field."
            })

    return violations


def assess_delta(delta: dict) -> dict:
    proposed_updates = delta.get("proposed_updates", {})

    known_concepts = proposed_updates.get("known_concepts", [])
    patterns = proposed_updates.get("reinforced_interaction_patterns", [])
    failure_patterns = proposed_updates.get("observed_failure_patterns", [])

    concept_assessment = assess_known_concepts(known_concepts)
    pattern_assessment = assess_patterns(patterns)
    failure_pattern_assessment = assess_patterns(failure_patterns)
    protected_field_violations = detect_protected_field_attempts(delta)

    approved_update_count = (
        len(concept_assessment["approved"])
        + len(pattern_assessment["approved"])
        + len(failure_pattern_assessment["approved"])
    )

    rejected_update_count = (
        len(concept_assessment["rejected"])
        + len(pattern_assessment["rejected"])
        + len(failure_pattern_assessment["rejected"])
        + len(protected_field_violations)
    )

    if protected_field_violations:
        decision = "rejected"
    elif approved_update_count > 0:
        decision = "approved_with_constraints"
    else:
        decision = "rejected"

    return {
        "event_type": "persona_delta_assessment",
        "schema_version": "0.1",
        "assessment_id": str(uuid4()),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "delta_id": delta.get("delta_id"),
        "persona": delta.get("persona", {}),
        "decision": decision,
        "summary": {
            "approved_update_count": approved_update_count,
            "rejected_update_count": rejected_update_count,
            "protected_field_violation_count": len(protected_field_violations),
        },
        "approved_updates": {
            "known_concepts": concept_assessment["approved"],
            "reinforced_interaction_patterns": pattern_assessment["approved"],
            "observed_failure_patterns": failure_pattern_assessment["approved"],
        },
        "rejected_updates": {
            "known_concepts": concept_assessment["rejected"],
            "reinforced_interaction_patterns": pattern_assessment["rejected"],
            "observed_failure_patterns": failure_pattern_assessment["rejected"],
            "protected_field_violations": protected_field_violations,
        },
        "governance": {
            "auto_apply": False,
            "requires_human_or_assessor_review": True,
            "reason": "Assessment approves only bounded engram-style updates. Application requires a separate apply step.",
        },
    }


def main():
    parser = argparse.ArgumentParser(
        description="Assess a proposed persona delta."
    )

    parser.add_argument(
        "delta_file",
        help="Path to a persona delta JSON file."
    )

    parser.add_argument(
        "--output-dir",
        default=DEFAULT_OUTPUT_DIR,
        help="Directory where assessment reports are written."
    )

    args = parser.parse_args()

    delta_path = Path(args.delta_file)
    output_dir = Path(args.output_dir)

    delta = load_json(delta_path)
    assessment = assess_delta(delta)

    output_dir.mkdir(parents=True, exist_ok=True)

    persona_id = assessment.get("persona", {}).get("persona_id", "unknown_persona")
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output_path = output_dir / f"{persona_id}_delta_assessment_{timestamp}.json"

    with output_path.open("w", encoding="utf-8") as f:
        json.dump(assessment, f, indent=2, ensure_ascii=False)

    print("Persona delta assessment generated:")
    print(output_path)
    print(f"Decision: {assessment['decision']}")


if __name__ == "__main__":
    main()