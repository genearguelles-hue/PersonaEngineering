import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from persona_test_harness.event_validator import (
    load_json,
    validate_persona_test_event,
)


EVENT_PATH = PROJECT_ROOT / "tests" / "sample_persona_test_event.json"


def main() -> int:
    try:
        event = load_json(EVENT_PATH)
        errors = validate_persona_test_event(event)

        if errors:
            print("❌ persona_test_event validation failed:\n")
            for error in errors:
                print(f"- {error}")
            return 1

        print("✅ persona_test_event is valid.")
        return 0

    except Exception as error:
        print(f"❌ Validation error: {error}")
        return 1


if __name__ == "__main__":
    sys.exit(main())