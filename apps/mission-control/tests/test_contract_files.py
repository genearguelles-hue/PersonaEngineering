from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ContractFileTests(unittest.TestCase):
    def test_tool_adapter_schema_is_valid_json(self) -> None:
        schema = json.loads(
            (ROOT / "contracts" / "tool-adapter.v1.schema.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(schema["properties"]["schema_version"]["const"], "pe.tool-adapter.v1")
        self.assertIn("execute", schema["properties"]["operations"]["items"]["enum"])
        self.assertIn("record_telemetry", schema["properties"]["operations"]["items"]["enum"])

    def test_canonical_example_is_pe_mission_v1(self) -> None:
        example = json.loads(
            (
                ROOT
                / "examples"
                / "selenium_saucedemo_checkout_governed.json"
            ).read_text(encoding="utf-8")
        )
        self.assertEqual(example["schema_version"], "pe.mission.v1")
        self.assertEqual(example["mission_type"], "ui_test")
        self.assertEqual(example["tool_request"]["tool"], "selenium")
        self.assertEqual(example["governance"]["mode"], "governed")

    def test_persona_governance_contracts_are_proposal_only(self) -> None:
        incident = json.loads(
            (ROOT / "contracts" / "behavioral-incident.v1.schema.json").read_text(
                encoding="utf-8"
            )
        )
        proposal = json.loads(
            (
                ROOT / "contracts" / "persona-delta-proposal.v1.schema.json"
            ).read_text(encoding="utf-8")
        )
        comparison = json.loads(
            (
                ROOT
                / "contracts"
                / "persona-regression-comparison.v1.schema.json"
            ).read_text(encoding="utf-8")
        )
        self.assertEqual(
            incident["properties"]["schema_version"]["const"],
            "pe.behavioral-incident.v1",
        )
        self.assertEqual(
            proposal["properties"]["application_status"]["const"],
            "not_applied",
        )
        self.assertEqual(
            comparison["properties"]["schema_version"]["const"],
            "pe.persona-regression-comparison.v1",
        )


if __name__ == "__main__":
    unittest.main()
