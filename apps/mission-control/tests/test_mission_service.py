from __future__ import annotations

import asyncio
import json
import os
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONTROLLER_ROOT = PROJECT_ROOT / "controller"
os.sys.path.insert(0, str(CONTROLLER_ROOT))

from pe_mission_control.adapters import SeleniumPeCliAdapter
from pe_mission_control.config import Settings
from pe_mission_control.ledger import MissionLedger
from pe_mission_control.mission_service import MissionService
from pe_mission_control.registry import AdapterRegistry


def load_example() -> dict:
    path = PROJECT_ROOT / "examples" / "mission_control_selenium_launch_request.json"
    return json.loads(path.read_text(encoding="utf-8"))


class MissionControlTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        settings = Settings(
            host="127.0.0.1",
            port=8765,
            execution_mode="fixture",
            persona_engineering_root=None,
            python_executable="python3",
            data_dir=Path(self.temp_dir.name),
        )
        registry = AdapterRegistry()
        registry.register(SeleniumPeCliAdapter(settings))
        self.registry = registry
        self.ledger = MissionLedger(settings.data_dir)
        self.service = MissionService(registry, self.ledger)

    async def asyncTearDown(self) -> None:
        self.temp_dir.cleanup()

    async def test_example_contract_is_valid(self) -> None:
        result = self.service.validate(load_example())
        self.assertTrue(result.valid, result.errors)
        self.assertEqual(
            result.normalized["schema_version"],
            "pe.mission-control.launch.v1",
        )
        self.assertEqual(result.normalized["tool"]["adapter_id"], "selenium")

    async def test_unknown_adapter_is_rejected(self) -> None:
        payload = load_example()
        payload["tool"]["adapter_id"] = "not-installed"
        payload["mission_type"] = "api_test"
        result = self.service.validate(payload)
        self.assertFalse(result.valid)
        self.assertIn("Unknown adapter", result.errors[0])

    async def test_governed_fixture_mission_completes_and_seals(self) -> None:
        record = await self.service.create(load_example())
        self.assertEqual(record.authorization.decision, "AUTHORIZED")
        self.assertTrue(record.mission_id.startswith("pe-mc-"))

        mission_path = self.ledger.mission_dir(record.mission_id) / "mission.json"
        canonical = json.loads(mission_path.read_text(encoding="utf-8"))
        self.assertEqual(canonical["mission_type"], "ui_test")
        self.assertEqual(canonical["tool_request"]["tool"], "selenium")
        self.assertEqual(canonical["governance"]["mode"], "governed")
        self.assertIn("planner", canonical["persona_bindings"])
        self.assertIn("assessor", canonical["persona_bindings"])

        for _ in range(40):
            current = self.service.get(record.mission_id)
            if current.state in {"completed", "failed", "cancelled"}:
                break
            await asyncio.sleep(0.05)

        current = self.service.get(record.mission_id)
        self.assertEqual(current.state, "completed")
        self.assertTrue(current.result.fixture)
        self.assertEqual(current.result.telemetry.total_tokens, 1024)

        events = self.service.events(record.mission_id)
        self.assertEqual(events[0]["event_type"], "MISSION_ACCEPTED")
        self.assertEqual(events[-1]["event_type"], "MISSION_TERMINATED")
        self.assertGreaterEqual(len(events), 6)

        verification = self.ledger.verify(record.mission_id)
        self.assertTrue(verification["valid"])
        manifest = self.service.evidence(record.mission_id)
        self.assertTrue(manifest["ledger"]["valid"])
        self.assertGreaterEqual(len(manifest["artifacts"]), 4)

    async def test_ungoverned_mode_is_explicitly_recorded(self) -> None:
        payload = load_example()
        payload["governance_mode"] = "ungoverned"
        record = await self.service.create(payload)
        self.assertEqual(record.authorization.decision, "BYPASSED")
        events = self.service.events(record.mission_id)
        self.assertEqual(events[1]["details"]["decision"], "BYPASSED")


if __name__ == "__main__":
    unittest.main()
