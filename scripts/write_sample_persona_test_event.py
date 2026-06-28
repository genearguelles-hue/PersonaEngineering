import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from persona_test_harness.event_validator import load_json
from persona_test_harness.ledger_writer import write_persona_test_event


EVENT_PATH = PROJECT_ROOT / "tests" / "sample_persona_test_event.json"
LEDGER_PATH = PROJECT_ROOT / "persona_ledger" / "persona_test_events.jsonl"


def main() -> int:
    try:
        event = load_json(EVENT_PATH)
        error = write_persona_test_event(event, LEDGER_PATH)

        if error:
            print("❌ Ledger write failed. Event is invalid:\n")
            print(error)
            return 1

        print(f"✅ Event written to Ledger: {LEDGER_PATH}")
        return 0

    except Exception as exc:
        print(f"❌ Ledger write error: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())