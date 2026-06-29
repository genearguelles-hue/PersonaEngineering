from pathlib import Path
from typing import Optional

from persona_test_harness.assessor import apply_assessment
from persona_test_harness.event_capture import create_persona_test_event
from persona_test_harness.ledger_writer import write_persona_test_event
from persona_test_harness.persona_loader import enrich_event_with_persona_parameters


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PERSONAS_DIR = PROJECT_ROOT / "personas"
LEDGER_PATH = PROJECT_ROOT / "persona_ledger" / "persona_test_events.jsonl"


def record_persona_interaction(
    persona_id: str,
    persona_name: str,
    user_input: str,
    persona_output: str,
    session_id: str,
    turn_index: int,
    persona_version: str = "0.1",
    context_summary: str = "",
    scenario_id: str = "",
    scenario_description: str = "",
) -> Optional[str]:
    """
    Captures, enriches, assesses, validates, and writes a persona interaction
    to the Persona Ledger.

    Returns:
        None if successful.
        Error message string if validation or recording fails.
    """

    try:
        event = create_persona_test_event(
            persona_id=persona_id,
            persona_name=persona_name,
            persona_version=persona_version,
            session_id=session_id,
            turn_index=turn_index,
            user_input=user_input,
            persona_output=persona_output,
            context_summary=context_summary,
            test_tags=["live_interaction", "auto_recorded"],
            scenario_id=scenario_id,
            scenario_description=scenario_description,
        )

        event = enrich_event_with_persona_parameters(event, PERSONAS_DIR)
        event = apply_assessment(event)

        error = write_persona_test_event(event, LEDGER_PATH)

        if error:
            return error

        return None

    except Exception as exc:
        return str(exc)