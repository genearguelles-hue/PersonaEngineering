#!/usr/bin/env python3
"""
Apply an approved Persona Delta Assessment to produce Persona(t+1).

This script creates a new persona version file.

It does NOT modify the original persona.json in place.

Formula:
Persona(t+1) = Persona(t) + Δ(Approved Experience)
"""

import argparse
import json
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path


DEFAULT_OUTPUT_DIR = "persona_memory/persona_versions"


def load_json(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def unique_merge(existing: list, incoming: list) -> list:
    result = []

    for item in existing + incoming:
        if item not in result:
            result.append(item)

    return result


def get_persona_block(persona_doc: dict) -> dict:
    if "persona" not in persona_doc or not isinstance(persona_doc["persona"], dict):
        persona_doc["persona"] = {}

    return persona_doc["persona"]


def apply_assessment(persona_doc: dict, assessment: dict) -> dict:
    decision = assessment.get("decision")

    if decision not in {"approved", "approved_with_constraints"}:
        raise ValueError(f"Assessment is not approved. Decision: {decision}")

    updated = deepcopy(persona_doc)
    persona_block = get_persona_block(updated)

    approved_updates = assessment.get("approved_updates", {})

    memory = persona_block.get("experienceDerivedMemory", {})

    memory["knownConcepts"] = unique_merge(
        memory.get("knownConcepts", []),
        approved_updates.get("known_concepts", [])
    )

    memory["reinforcedInteractionPatterns"] = unique_merge(
        memory.get("reinforcedInteractionPatterns", []),
        approved_updates.get("reinforced_interaction_patterns", [])
    )

    memory["observedFailurePatterns"] = unique_merge(
        memory.get("observedFailurePatterns", []),
        approved_updates.get("observed_failure_patterns", [])
    )

    memory["lastUpdatedAt"] = datetime.now(timezone.utc).isoformat()
    memory["lastUpdatedFromAssessment"] = assessment.get("assessment_id")
    memory["lastAppliedDeltaId"] = assessment.get("delta_id")

    persona_block["experienceDerivedMemory"] = memory

    update_history = persona_block.get("personaUpdateHistory", [])

    update_history.append({
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "assessment_id": assessment.get("assessment_id"),
        "delta_id": assessment.get("delta_id"),
        "decision": decision,
        "applied_fields": [
            "experienceDerivedMemory.knownConcepts",
            "experienceDerivedMemory.reinforcedInteractionPatterns",
            "experienceDerivedMemory.observedFailurePatterns",
        ],
        "protected_fields_modified": False,
    })

    persona_block["personaUpdateHistory"] = update_history

    updated["schemaVersion"] = updated.get("schemaVersion", "0.1")
    updated["persona"] = persona_block

    return updated


def infer_persona_id(persona_doc: dict, assessment: dict) -> str:
    return (
        assessment.get("persona", {}).get("persona_id")
        or persona_doc.get("persona", {}).get("persona_id")
        or persona_doc.get("persona", {}).get("name", "unknown_persona")
            .lower()
            .replace(" ", "_")
    )


def main():
    parser = argparse.ArgumentParser(
        description="Apply an approved persona delta assessment to create Persona(t+1)."
    )

    parser.add_argument(
        "persona_file",
        help="Path to the current persona JSON file."
    )

    parser.add_argument(
        "assessment_file",
        help="Path to an approved persona delta assessment JSON file."
    )

    parser.add_argument(
        "--output-dir",
        default=DEFAULT_OUTPUT_DIR,
        help="Directory where new persona versions are written."
    )

    args = parser.parse_args()

    persona_path = Path(args.persona_file)
    assessment_path = Path(args.assessment_file)
    output_dir = Path(args.output_dir)

    persona_doc = load_json(persona_path)
    assessment = load_json(assessment_path)

    updated_persona = apply_assessment(persona_doc, assessment)

    output_dir.mkdir(parents=True, exist_ok=True)

    persona_id = infer_persona_id(persona_doc, assessment)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    output_path = output_dir / f"{persona_id}_persona_vnext_{timestamp}.json"

    with output_path.open("w", encoding="utf-8") as f:
        json.dump(updated_persona, f, indent=2, ensure_ascii=False)

    print("Persona(t+1) generated:")
    print(output_path)


if __name__ == "__main__":
    main()