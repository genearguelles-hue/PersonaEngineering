import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from persona_test_harness.report_generator import generate_report_from_ledger


LEDGER_PATH = PROJECT_ROOT / "persona_ledger" / "persona_test_events.jsonl"
REPORTS_DIR = PROJECT_ROOT / "reports"
REPORT_PATH = REPORTS_DIR / "persona_test_report.md"


def main() -> int:
    try:
        event_count = generate_report_from_ledger(
            ledger_path=LEDGER_PATH,
            report_path=REPORT_PATH
        )

        print(f"✅ Report generated: {REPORT_PATH}")
        print(f"Events included: {event_count}")
        return 0

    except Exception as exc:
        print(f"❌ Report generation failed: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())