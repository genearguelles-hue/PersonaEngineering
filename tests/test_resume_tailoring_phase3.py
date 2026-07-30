from __future__ import annotations

import hashlib
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
    ResumePurgeRequest,
    ResumeWorkflowState,
)
from pe_mission_control.resume_workflow import (
    ResumeWorkflowConflictError,
    ResumeWorkflowService,
)


REPO_ROOT = Path(__file__).resolve().parents[1]


class ResumeTailoringPhase3Test(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        root = Path(self.temporary.name)
        self.intake = root / "intake"
        self.intake.mkdir()
        self.data_dir = root / "data"
        self.ledger = MissionLedger(self.data_dir)
        self.registry = AdapterRegistry()
        self.adapter = ResumeTailoringAdapter(
            SimpleNamespace(
                execution_mode="fixture",
                resume_intake_root=str(self.intake),
            )
        )
        self.registry.register(self.adapter)
        self.service = ResumeWorkflowService(
            self.registry,
            self.ledger,
            self.adapter,
        )
        self.candidate = {
            "schema_version": "pe.resume-candidate-profile.v1",
            "candidate": {
                "display_name": "Gene Test Candidate",
                "contact": {
                    "email": "gene.candidate@example.com",
                    "phone": "312-555-0188",
                    "location": "Chicago, Illinois",
                    "linkedin": "https://www.linkedin.com/in/gene-candidate",
                },
            },
            "summary": (
                "AI systems architect focused on governed automation, "
                "privacy, testing, and measurable operational efficiency."
            ),
            "skills": [
                "Python",
                "AI workflow automation",
                "data privacy",
                "test automation",
                "efficiency measurement",
            ],
            "experience": [
                {
                    "employer": "Private Candidate Employer",
                    "role_title": "AI Systems Architect",
                    "dates": "2024-present",
                    "bullets": [
                        {
                            "evidence_id": "fact-automation",
                            "text": (
                                "Built Python AI workflow automation with "
                                "governance and audit evidence."
                            ),
                        },
                        {
                            "evidence_id": "fact-privacy",
                            "text": (
                                "Implemented data privacy and confidentiality "
                                "controls for automated workflows."
                            ),
                        },
                        {
                            "evidence_id": "fact-efficiency",
                            "text": (
                                "Measured time saved and operational efficiency "
                                "from deployed test automation."
                            ),
                        },
                    ],
                }
            ],
            "education": [
                {
                    "credential": "Test Credential",
                    "institution": "Private Candidate University",
                }
            ],
        }
        self.job = {
            "schema_version": "pe.resume-job-description.v1",
            "employer": "Private Target Employer",
            "role_title": "AI Automation Engineer",
            "description": (
                "Build governed AI automation for internal legal workflows "
                "with privacy controls and measurable efficiency."
            ),
            "requirements": [
                {
                    "id": "req-automation",
                    "text": "Build Python AI workflow automation",
                    "required": True,
                },
                {
                    "id": "req-privacy",
                    "text": "Apply data privacy and confidentiality controls",
                    "required": True,
                },
                {
                    "id": "req-efficiency",
                    "text": "Measure time saved and operational efficiency",
                    "required": True,
                },
            ],
        }
        candidate_path = self.intake / "candidate_profile.json"
        job_path = self.intake / "job_description.json"
        self._write_json(candidate_path, self.candidate)
        self._write_json(job_path, self.job)
        self.payload = json.loads(
            (
                REPO_ROOT
                / "examples"
                / "resume"
                / "resume_tailoring_phase3_real_shadow.example.json"
            ).read_text(encoding="utf-8")
        )
        candidate_ref = self.payload["tool"]["parameters"]["resume_mission"][
            "candidate_source_refs"
        ][0]
        job_ref = self.payload["tool"]["parameters"]["resume_mission"][
            "target_job"
        ]["description_ref"]
        candidate_ref["content_hash"] = self._hash(candidate_path)
        job_ref["content_hash"] = self._hash(job_path)
        self.payload["tool"]["parameters"]["resume_mission"]["target_job"][
            "employer"
        ] = self.job["employer"]

    async def asyncTearDown(self) -> None:
        self.temporary.cleanup()

    async def test_real_shadow_approval_sanitization_and_purge(self) -> None:
        created = await self.service.create(self.payload)
        self.assertEqual(
            created.state,
            ResumeWorkflowState.AWAITING_USER_APPROVAL,
        )
        self.assertEqual(created.assessor_verdict, "pass")
        mission_dir = self.ledger.mission_dir(created.mission_id)
        draft = (mission_dir / "resume-draft.md").read_text(encoding="utf-8")
        self.assertIn("Gene Test Candidate", draft)
        self.assertIn("gene.candidate@example.com", draft)
        self.assertIn("Private Candidate Employer", draft)

        completed = self.service.decide(
            created.mission_id,
            ResumeDecisionRequest(
                decision="approve",
                reviewer_id="candidate-owner",
                notes="Approved for local shadow evaluation.",
            ),
        )
        self.assertEqual(completed.state, ResumeWorkflowState.COMPLETED)
        self.assertTrue(self.ledger.verify(created.mission_id)["valid"])
        self.assertIsNotNone(self.ledger.manifest(created.mission_id))

        chunks = (
            mission_dir / "ideation-chunks.sanitized.json"
        ).read_text(encoding="utf-8")
        embedding = (
            mission_dir / "ideation-embedding-manifest.json"
        ).read_text(encoding="utf-8")
        ledger_text = (
            mission_dir / "events.jsonl"
        ).read_text(encoding="utf-8")
        for prohibited in (
            "Gene Test Candidate",
            "gene.candidate@example.com",
            "312-555-0188",
            "Private Candidate Employer",
            "Private Target Employer",
            "Private Candidate University",
        ):
            self.assertNotIn(prohibited, chunks)
            self.assertNotIn(prohibited, embedding)
            self.assertNotIn(prohibited, ledger_text)
        self.assertIn('"production_vector_write": false', embedding)
        self.assertTrue((mission_dir / "retention-manifest.json").is_file())

        receipt = self.service.purge_sensitive(
            created.mission_id,
            ResumePurgeRequest(
                reviewer_id="candidate-owner",
                reason="Application artifact was exported and reviewed.",
                confirmation="PURGE_SENSITIVE_ARTIFACTS",
            ),
        )
        self.assertGreaterEqual(receipt["removed_artifact_count"], 4)
        for name in (
            "requirements.json",
            "evidence-map.json",
            "resume-draft.md",
            "resume-final.md",
        ):
            self.assertFalse((mission_dir / name).exists())
        self.assertTrue(
            (mission_dir / "ideation-chunks.sanitized.json").is_file()
        )
        events = self.ledger.events(created.mission_id)
        self.assertIn(
            "resume_sensitive_artifacts_purged",
            {item["event_type"] for item in events},
        )
        self.assertTrue(self.ledger.verify(created.mission_id)["valid"])
        manifest_paths = {
            item["path"]
            for item in self.ledger.manifest(created.mission_id)["artifacts"]
        }
        self.assertNotIn("resume-final.md", manifest_paths)

    async def test_missing_consent_is_blocked_before_source_resolution(self) -> None:
        self.payload["mission_id"] = "pe-resume-phase3-consent-blocked"
        controls = self.payload["tool"]["parameters"]["resume_mission"][
            "real_data_controls"
        ]
        controls["user_consent"] = False
        blocked = await self.service.create(self.payload)
        self.assertEqual(blocked.state, ResumeWorkflowState.FAILED)
        self.assertEqual(blocked.authorization_decision, "blocked")
        self.assertIn("user_consent", blocked.error)
        self.assertTrue(self.ledger.verify(blocked.mission_id)["valid"])

    async def test_hash_mismatch_fails_closed(self) -> None:
        self.payload["mission_id"] = "pe-resume-phase3-hash-blocked"
        self.payload["tool"]["parameters"]["resume_mission"][
            "candidate_source_refs"
        ][0]["content_hash"] = "0" * 64
        failed = await self.service.create(self.payload)
        self.assertEqual(failed.state, ResumeWorkflowState.FAILED)
        self.assertIn("content hash mismatch", failed.error)
        mission_dir = self.ledger.mission_dir(failed.mission_id)
        self.assertFalse((mission_dir / "resume-draft.md").exists())
        self.assertTrue(self.ledger.verify(failed.mission_id)["valid"])

    async def test_inline_real_source_content_is_rejected(self) -> None:
        reference = self.payload["tool"]["parameters"]["resume_mission"][
            "candidate_source_refs"
        ][0]
        reference["content"] = self.candidate
        with self.assertRaisesRegex(
            ResumeWorkflowConflictError,
            "inline content is not allowed",
        ):
            await self.service.create(self.payload)

    async def test_traversal_source_uri_fails_closed(self) -> None:
        self.payload["mission_id"] = "pe-resume-phase3-traversal-blocked"
        self.payload["tool"]["parameters"]["resume_mission"][
            "candidate_source_refs"
        ][0]["uri"] = "intake:///../candidate_profile.json"
        failed = await self.service.create(self.payload)
        self.assertEqual(failed.state, ResumeWorkflowState.FAILED)
        self.assertIn("traversing", failed.error)
        self.assertTrue(self.ledger.verify(failed.mission_id)["valid"])

    async def test_high_risk_identifier_in_source_fails_closed(self) -> None:
        self.payload["mission_id"] = "pe-resume-phase3-identifier-blocked"
        self.candidate["candidate"]["ssn"] = "123-45-6789"
        candidate_path = self.intake / "candidate_profile.json"
        self._write_json(candidate_path, self.candidate)
        self.payload["tool"]["parameters"]["resume_mission"][
            "candidate_source_refs"
        ][0]["content_hash"] = self._hash(candidate_path)
        failed = await self.service.create(self.payload)
        self.assertEqual(failed.state, ResumeWorkflowState.FAILED)
        self.assertIn("high-risk identifier", failed.error)
        self.assertFalse(
            (self.ledger.mission_dir(failed.mission_id) / "resume-draft.md").exists()
        )

    async def test_synthetic_phase2_path_remains_available(self) -> None:
        payload = json.loads(
            (
                REPO_ROOT
                / "examples"
                / "resume"
                / "resume_tailoring_phase2_synthetic.example.json"
            ).read_text(encoding="utf-8")
        )
        created = await self.service.create(payload)
        self.assertEqual(
            created.state,
            ResumeWorkflowState.AWAITING_USER_APPROVAL,
        )
        revised = self.service.decide(
            created.mission_id,
            ResumeDecisionRequest(
                decision="revise",
                reviewer_id="synthetic-reviewer",
                notes="Exercise the Phase 2 revision regression path.",
                corrections=["Emphasize evidence-bound workflow governance."],
            ),
        )
        self.assertEqual(
            revised.state,
            ResumeWorkflowState.AWAITING_USER_APPROVAL,
        )
        completed = self.service.decide(
            created.mission_id,
            ResumeDecisionRequest(
                decision="approve",
                reviewer_id="synthetic-reviewer",
                notes="Phase 2 regression path.",
            ),
        )
        self.assertEqual(completed.state, ResumeWorkflowState.COMPLETED)
        observed = {
            item["event_type"]
            for item in self.ledger.events(created.mission_id)
        }
        self.assertEqual(observed, set(ResumeWorkflowService.EVENT_TYPES))

    @staticmethod
    def _write_json(path: Path, value: dict) -> None:
        path.write_text(
            json.dumps(value, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    @staticmethod
    def _hash(path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()


if __name__ == "__main__":
    unittest.main()
