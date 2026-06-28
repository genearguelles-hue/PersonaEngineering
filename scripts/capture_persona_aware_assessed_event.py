import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from persona_test_harness.assessor import apply_assessment
from persona_test_harness.event_capture import create_persona_test_event
from persona_test_harness.ledger_writer import write_persona_test_event
from persona_test_harness.persona_loader import enrich_event_with_persona_parameters


LEDGER_PATH = PROJECT_ROOT / "persona_ledger" / "persona_test_events.jsonl"
PERSONAS_DIR = PROJECT_ROOT / "personas"


def main() -> int:
    try:
        event = create_persona_test_event(
            persona_id="the_structured_companion",
            persona_name="The Structured Companion",
            persona_version="0.1",
            session_id="manual_session_003",
            turn_index=1,
            user_input="Help me organize my thoughts into a project plan.",
            persona_output="Let's break the project into goals, constraints, milestones, risks, and next actions.",
            context_summary="User requested structured planning assistance.",
            test_tags=["development", "manual_capture", "assessed", "persona_aware", "planning"],
            scenario_id="SCN-PLANNING-003",
            scenario_description="Persona-aware assessment using loaded persona definition."
        )

        event = enrich_event_with_persona_parameters(event, PERSONAS_DIR)
        event = apply_assessment(event)

        error = write_persona_test_event(event, LEDGER_PATH)

        if error:
            print("❌ Persona-aware assessed event failed validation:")
            print(error)
            return 1

        print(f"✅ Persona-aware assessed event written to Ledger: {LEDGER_PATH}")
        print(f"Event ID: {event['event_id']}")
        print(f"Active axioms: {len(event['persona_parameters']['active_axioms'])}")
        print(f"Active primitives: {len(event['persona_parameters']['active_primitives'])}")
        print(f"Active engrams: {len(event['persona_parameters']['active_engrams'])}")
        print(f"Scores: {event['assessment']['scores']}")
        print(f"Violations: {len(event['assessment']['violations'])}")
        return 0

    except Exception as exc:
        print(f"❌ Persona-aware capture failed: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
    