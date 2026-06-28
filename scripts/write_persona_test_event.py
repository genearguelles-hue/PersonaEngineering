import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from persona_test_harness.event_validator import load_json
from persona_test_harness.ledger_writer import write_persona_test_event


DEFAULT_LEDGER_PATH = PROJECT_ROOT / "persona_ledger" / "persona_test_events.jsonl"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate and write a persona_test_event JSON file to the Ledger."
    )

    parser.add_argument(
        "event_file",
        help="Path to the persona_test_event JSON file to write."
    )

    parser.add_argument(
        "--ledger",
        default=str(DEFAULT_LEDGER_PATH),
        help="Path to the target Ledger JSONL file."
    )

    args = parser.parse_args()

    event_path = Path(args.event_file)
    ledger_path = Path(args.ledger)

    try:
        event = load_json(event_path)
        error = write_persona_test_event(event, ledger_path)

        if error:
            print("❌ Ledger write failed. Event is invalid:\n")
            print(error)
            return 1

        print(f"✅ Event written to Ledger: {ledger_path}")
        return 0

    except Exception as exc:
        print(f"❌ Ledger write error: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())