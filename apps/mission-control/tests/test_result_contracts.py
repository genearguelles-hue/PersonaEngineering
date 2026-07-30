from __future__ import annotations

import json
import os
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONTROLLER_ROOT = PROJECT_ROOT / "controller"
os.sys.path.insert(0, str(CONTROLLER_ROOT))

from pe_mission_control.result_contracts import (
    ResultContractError,
    normalize_selenium_summary,
    verify_selenium_result_contract,
)


def load_real_envelope() -> dict:
    return json.loads(
        (
            PROJECT_ROOT
            / "tests"
            / "fixtures"
            / "selenium_pe_test_run_envelope.json"
        ).read_text(encoding="utf-8")
    )


class SeleniumResultContractTests(unittest.TestCase):
    def test_real_pe_test_envelope_normalizes_to_two_passes(self) -> None:
        normalized = normalize_selenium_summary(load_real_envelope())
        self.assertEqual(normalized["total"], 2)
        self.assertEqual(normalized["passed"], 2)
        self.assertEqual(normalized["failed"], 0)
        self.assertAlmostEqual(normalized["duration_seconds"], 77.427)

    def test_real_pe_test_envelope_satisfies_mission_criteria(self) -> None:
        verification = verify_selenium_result_contract(
            load_real_envelope(),
            minimum_passed_tests=2,
            maximum_duration_seconds=120,
            require_zero_failures=True,
        )
        self.assertTrue(verification["valid"])
        self.assertTrue(all(item["passed"] for item in verification["checks"]))

    def test_inconsistent_counts_are_rejected(self) -> None:
        payload = load_real_envelope()
        payload["summary"]["tests"] = 1
        payload["summary"]["failures"] = 1
        payload["summary"]["skipped"] = 1
        with self.assertRaises(ResultContractError):
            normalize_selenium_summary(payload)


if __name__ == "__main__":
    unittest.main()
