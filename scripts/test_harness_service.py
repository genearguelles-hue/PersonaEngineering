import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from persona_test_harness.harness_service import record_persona_interaction


def main() -> int:
    error = record_persona_interaction(
        persona_id="the_structured_companion",
        persona_name="The Structured Companion",
        persona_version="0.1",
        session_id="service_test_001",
        turn_index=1,
        user_input="Help me turn this idea into a project plan.",
        persona_output="We can structure it into objectives, constraints, milestones, risks, and next actions.",
        context_summary="Service-level test of automatic persona interaction recording.",
        scenario_id="SCN-SERVICE-001",
        scenario_description="Harness service integration smoke test."
    )

    if error:
        print("❌ Harness service test failed:")
        print(error)
        return 1

    print("✅ Harness service test succeeded.")
    return 0


if __name__ == "__main__":
    sys.exit(main())