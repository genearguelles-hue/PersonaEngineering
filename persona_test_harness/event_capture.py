from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def create_persona_test_event(
    persona_id: str,
    persona_name: str,
    user_input: str,
    persona_output: str,
    session_id: str,
    turn_index: int,
    persona_version: str = "0.1",
    context_summary: str = "",
    test_mode: str = "normal_interaction",
    test_tags: Optional[List[str]] = None,
    scenario_id: str = "",
    scenario_description: str = "",
) -> Dict[str, Any]:
    return {
        "event_type": "persona_test_event",
        "schema_version": "0.1",
        "event_id": str(uuid4()),
        "timestamp": utc_now_iso(),

        "persona": {
            "persona_id": persona_id,
            "persona_name": persona_name,
            "persona_version": persona_version
        },

        "interaction": {
            "session_id": session_id,
            "turn_index": turn_index,
            "user_input": user_input,
            "persona_output": persona_output,
            "context_summary": context_summary
        },

        "persona_parameters": {
            "active_axioms": [],
            "active_primitives": [],
            "active_engrams": []
        },

        "test_metadata": {
            "test_mode": test_mode,
            "test_tags": test_tags or ["development", "manual_capture"],
            "scenario_id": scenario_id,
            "scenario_description": scenario_description
        },

        "assessment": {
            "assessor_id": "manual_assessor_v0",
            "assessor_version": "0.1",
            "scores": {
                "axiom_compliance": 1.0,
                "primitive_alignment": 1.0,
                "persona_coherence": 1.0,
                "response_quality": 1.0,
                "drift_risk": 0.0,
                "safety_risk": 0.0
            },
            "violations": [],
            "assessor_notes": "Initial manually captured event. No automated assessment yet."
        },

        "governance": {
            "action_taken": "none",
            "human_review_required": False,
            "review_status": "not_required",
            "governance_notes": "No governance intervention required."
        },

        "ledger": {
            "previous_event_id": None,
            "linked_events": [],
            "hash": None
        }
    }