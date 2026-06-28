import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from persona_test_harness.event_capture import create_persona_test_event
from persona_test_harness.ledger_writer import write_persona_test_event


LEDGER_PATH = PROJECT_ROOT / "persona_ledger" / "persona_test_events.jsonl"


def main() -> int:
    event = create_persona_test_event(
        persona_id="the_structured_companion",
        persona_name="The Structured Companion",
        persona_version="0.1",
        session_id="manual_session_001",
        turn_index=1,
        user_input="Help me organize my thoughts into a project plan.",
        persona_output="Let's break the project into goals, constraints, milestones, risks, and next actions.",
        context_summary="User requested structured planning assistance.",
        test_tags=["development", "manual_capture", "planning"],
        scenario_id="SCN-PLANNING-001",
        scenario_description="Baseline structured planning interaction."
    )

    error = write_persona_test_event(event, LEDGER_PATH)

    if error:
        print("❌ Captured event failed validation:")
        print(error)
        return 1

    print(f"✅ Captured event written to Ledger: {LEDGER_PATH}")
    print(f"Event ID: {event['event_id']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())