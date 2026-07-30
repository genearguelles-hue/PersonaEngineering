from __future__ import annotations

import json
from pathlib import Path

from pe_mission.assessor import _normalized_selenium_summary


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "selenium_pe_test_run_envelope.json"


def main() -> int:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    passed, failed, duration = _normalized_selenium_summary(payload)
    verification = {
        "schema_version": "pe.selenium-result-contract-patch-check.v1",
        "decision": (
            "valid"
            if passed == 2 and failed == 0 and round(duration, 3) == 77.427
            else "invalid"
        ),
        "observed": {
            "passed_tests": passed,
            "failed_tests": failed,
            "duration_seconds": round(duration, 3),
        },
        "expected": {
            "passed_tests": 2,
            "failed_tests": 0,
            "duration_seconds": 77.427,
        },
    }
    print(json.dumps(verification, indent=2))
    return 0 if verification["decision"] == "valid" else 1


if __name__ == "__main__":
    raise SystemExit(main())
