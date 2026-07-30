from __future__ import annotations

import json
import os
import tempfile
import time
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONTROLLER_ROOT = PROJECT_ROOT / "controller"
os.sys.path.insert(0, str(CONTROLLER_ROOT))

from fastapi.testclient import TestClient

import pe_mission_control.app as app_module
from pe_mission_control.adapters import SeleniumPeCliAdapter
from pe_mission_control.config import Settings
from pe_mission_control.ledger import MissionLedger
from pe_mission_control.mission_service import MissionService
from pe_mission_control.persona_governance import PersonaGovernanceStore
from pe_mission_control.registry import AdapterRegistry


def load_example() -> dict:
    path = PROJECT_ROOT / "examples" / "mission_control_selenium_launch_request.json"
    return json.loads(path.read_text(encoding="utf-8"))


class ControlApiTests(unittest.TestCase):
    def setUp(self) -> None:
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
        app_module.settings = settings
        app_module.registry = registry
        app_module.ledger = MissionLedger(settings.data_dir)
        app_module.missions = MissionService(registry, app_module.ledger)
        app_module.persona_governance = PersonaGovernanceStore(settings.data_dir)
        self.client = TestClient(app_module.app)
        self.client.__enter__()

    def tearDown(self) -> None:
        self.client.__exit__(None, None, None)
        self.temp_dir.cleanup()

    def test_health_and_adapter_discovery(self) -> None:
        health = self.client.get("/api/v1/health")
        self.assertEqual(health.status_code, 200)
        self.assertEqual(health.json()["execution_mode"], "fixture")
        self.assertEqual(health.json()["adapters"][0]["adapter_id"], "selenium")

        adapters = self.client.get("/api/v1/adapters")
        self.assertEqual(adapters.status_code, 200)
        self.assertIn("pe.mission.v1", adapters.json()[0]["capabilities"])

    def test_mission_endpoint_accepts_contract(self) -> None:
        response = self.client.post("/api/v1/missions", json=load_example())
        self.assertEqual(response.status_code, 202, response.text)
        mission_id = response.json()["mission_id"]
        self.assertTrue(mission_id.startswith("pe-mc-"))

        deadline = time.monotonic() + 3
        record = response.json()
        while time.monotonic() < deadline:
            record_response = self.client.get(f"/api/v1/missions/{mission_id}")
            self.assertEqual(record_response.status_code, 200)
            record = record_response.json()
            if record["state"] in {"completed", "failed", "cancelled"}:
                break
            time.sleep(0.05)

        self.assertEqual(record["state"], "completed")
        events = self.client.get(f"/api/v1/missions/{mission_id}/events")
        self.assertEqual(events.status_code, 200)
        self.assertGreaterEqual(len(events.json()), 6)
        evidence = self.client.get(f"/api/v1/missions/{mission_id}/evidence")
        self.assertEqual(evidence.status_code, 200)
        self.assertTrue(evidence.json()["ledger"]["valid"])

    def test_persona_delta_is_proposal_only_and_audited(self) -> None:
        incident_response = self.client.post(
            "/api/v1/behavioral-incidents",
            json={
                "persona_id": "test-executor",
                "persona_version": "1.0.0",
                "classification": "behavioral_deviation",
                "title": "Result verification omitted",
                "description": (
                    "The persona accepted an unnormalized result without checking "
                    "the authoritative evidence vocabulary."
                ),
                "evidence_refs": ["artifact:tool-result.json"],
                "reported_by": "test-operator",
            },
        )
        self.assertEqual(incident_response.status_code, 201, incident_response.text)
        incident_id = incident_response.json()["incident_id"]

        proposal_response = self.client.post(
            "/api/v1/persona-delta-proposals",
            json={
                "incident_id": incident_id,
                "persona_id": "test-executor",
                "base_version": "1.0.0",
                "proposed_version": "1.0.1",
                "title": "Verify normalized execution evidence",
                "hypothesis": (
                    "Explicit result-contract verification prevents acceptance "
                    "of semantically incompatible evidence."
                ),
                "primitive_changes": [
                    {
                        "primitive_id": "execution.verify_result_contract",
                        "operation": "replace",
                        "current_value": "optional",
                        "proposed_value": "required",
                        "rationale": "Make evidence vocabulary validation explicit.",
                    }
                ],
                "safety_constraints": ["Preserve persona axioms."],
                "regression_objectives": ["Maintain boundary compliance."],
                "proposed_by": "test-operator",
            },
        )
        self.assertEqual(proposal_response.status_code, 201, proposal_response.text)
        proposal_id = proposal_response.json()["proposal_id"]
        self.assertEqual(proposal_response.json()["application_status"], "not_applied")

        review_response = self.client.post(
            f"/api/v1/persona-delta-proposals/{proposal_id}/review",
            json={
                "decision": "approve",
                "reviewer_id": "human-reviewer",
                "notes": "Approved as a candidate for regression testing.",
            },
        )
        self.assertEqual(review_response.status_code, 200, review_response.text)
        self.assertEqual(review_response.json()["status"], "approved")
        self.assertEqual(review_response.json()["application_status"], "not_applied")

        comparison_response = self.client.post(
            f"/api/v1/persona-delta-proposals/{proposal_id}/regression-comparisons",
            json={
                "metrics": [
                    {
                        "metric": "mission_alignment",
                        "baseline": 0.8,
                        "candidate": 0.9,
                        "unit": "score",
                        "objective": "increase",
                        "passed": True,
                    }
                ],
                "verdict": "pass",
                "notes": "Candidate improved without a boundary regression.",
                "recorded_by": "test-operator",
            },
        )
        self.assertEqual(comparison_response.status_code, 201)

        versions_response = self.client.get(
            "/api/v1/personas/test-executor/versions"
        )
        self.assertEqual(versions_response.status_code, 200)
        versions = versions_response.json()
        self.assertEqual([item["version"] for item in versions], ["1.0.0", "1.0.1"])
        self.assertTrue(versions[1]["approved"])
        self.assertFalse(versions[1]["applied"])

        self.assertEqual(
            self.client.post(
                f"/api/v1/persona-delta-proposals/{proposal_id}/apply"
            ).status_code,
            404,
        )
        integrity = self.client.get("/api/v1/persona-governance/integrity")
        self.assertTrue(integrity.json()["valid"])
        self.assertEqual(integrity.json()["event_count"], 4)


if __name__ == "__main__":
    unittest.main()
