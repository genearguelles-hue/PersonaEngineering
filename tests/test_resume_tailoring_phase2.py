from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from pe_mission_control.adapters.resume_tailor import ResumeTailoringAdapter
from pe_mission_control.ledger import MissionLedger
from pe_mission_control.registry import AdapterRegistry
from pe_mission_control.resume_models import (
    ResumeDecisionRequest,
    ResumeWorkflowState,
)
from pe_mission_control.resume_workflow import ResumeWorkflowService


REPO_ROOT = Path(__file__).resolve().parents[1]


class ResumeTailoringPhase2Test(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        data_dir = Path(self.temporary.name)
        self.ledger = MissionLedger(data_dir)
        self.registry = AdapterRegistry()
        self.adapter = ResumeTailoringAdapter(
            SimpleNamespace(execution_mode="fixture")
        )
        self.registry.register(self.adapter)
        self.service = ResumeWorkflowService(
            self.registry,
            self.ledger,
            self.adapter,
        )
        self.payload = json.loads(
            (
                REPO_ROOT
                / "examples"
                / "resume"
                / "resume_tailoring_phase2_synthetic.example.json"
            ).read_text(encoding="utf-8")
        )

    async def asyncTearDown(self) -> None:
        self.temporary.cleanup()

    async def test_full_revision_approval_and_ideation_path(self) -> None:
        created = await self.service.create(self.payload)
        self.assertEqual(
            created.state,
            ResumeWorkflowState.AWAITING_USER_APPROVAL,
        )
        self.assertEqual(created.assessor_verdict, "pass")
        self.assertIsNone(self.ledger.manifest(created.mission_id))

        revised = self.service.decide(
            created.mission_id,
            ResumeDecisionRequest(
                decision="revise",
                reviewer_id="synthetic-reviewer",
                notes="Exercise the controlled revision path.",
                corrections=[
                    "Emphasize evidence-bound workflow governance."
                ],
            ),
        )
        self.assertEqual(
            revised.state,
            ResumeWorkflowState.AWAITING_USER_APPROVAL,
        )
        self.assertEqual(revised.revision_count, 1)

        completed = self.service.decide(
            created.mission_id,
            ResumeDecisionRequest(
                decision="approve",
                reviewer_id="synthetic-reviewer",
                notes="Synthetic fixture approved.",
            ),
        )
        self.assertEqual(completed.state, ResumeWorkflowState.COMPLETED)
        events = self.ledger.events(created.mission_id)
        observed_types = {item["event_type"] for item in events}
        self.assertEqual(
            observed_types,
            set(ResumeWorkflowService.EVENT_TYPES),
        )
        self.assertTrue(self.ledger.verify(created.mission_id)["valid"])
        manifest = self.ledger.manifest(created.mission_id)
        self.assertIsNotNone(manifest)
        self.assertTrue(manifest["ledger"]["valid"])

        mission_dir = self.ledger.mission_dir(created.mission_id)
        embedding_text = (
            mission_dir / "ideation-embedding-manifest.json"
        ).read_text(encoding="utf-8")
        chunk_text = (
            mission_dir / "ideation-chunks.sanitized.json"
        ).read_text(encoding="utf-8")
        for prohibited in (
            "@",
            "555-",
            "social security",
            "api_key",
            "Administered production Kubernetes clusters",
        ):
            self.assertNotIn(prohibited, embedding_text)
            self.assertNotIn(prohibited, chunk_text)
        self.assertTrue((mission_dir / "resume-final.md").is_file())

    async def test_non_fixture_mission_is_blocked(self) -> None:
        self.payload["mission_id"] = "pe-resume-phase2-blocked-001"
        self.payload["tool"]["parameters"]["fixture"] = False
        blocked = await self.service.create(self.payload)
        self.assertEqual(blocked.state, ResumeWorkflowState.FAILED)
        self.assertEqual(blocked.authorization_decision, "blocked")
        self.assertTrue(self.ledger.verify(blocked.mission_id)["valid"])
        self.assertIsNotNone(self.ledger.manifest(blocked.mission_id))

    async def test_revision_rejects_pii(self) -> None:
        self.payload["mission_id"] = "pe-resume-phase2-pii-001"
        created = await self.service.create(self.payload)
        with self.assertRaisesRegex(Exception, "PII or secret"):
            self.service.decide(
                created.mission_id,
                ResumeDecisionRequest(
                    decision="revise",
                    reviewer_id="synthetic-reviewer",
                    corrections=["Contact candidate@example.com"],
                ),
            )


if __name__ == "__main__":
    unittest.main()
