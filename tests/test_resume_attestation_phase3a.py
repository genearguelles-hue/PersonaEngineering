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
from pe_mission_control.resume_attestation import (
    ResumePersonaBindingError,
    ResumePersonaRegistry,
)
from pe_mission_control.resume_models import (
    ResumeDecisionRequest,
    ResumePurgeRequest,
    ResumeWorkflowState,
)
from pe_mission_control.resume_workflow import ResumeWorkflowService


REPO_ROOT = Path(__file__).resolve().parents[1]
PERSONA_PATH = (
    REPO_ROOT / "personas" / "resume_tailoring_specialist.persona.json"
)


class ResumeAttestationPhase3ATest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        root = Path(self.temporary.name)
        self.intake = root / "intake"
        self.intake.mkdir()
        self.ledger = MissionLedger(root / "data")
        settings = SimpleNamespace(
            execution_mode="fixture",
            resume_intake_root=str(self.intake),
            persona_registry_root=str(REPO_ROOT),
        )
        self.registry = AdapterRegistry()
        self.adapter = ResumeTailoringAdapter(settings)
        self.registry.register(self.adapter)
        self.service = ResumeWorkflowService(
            self.registry,
            self.ledger,
            self.adapter,
        )
        candidate = {
            "schema_version": "pe.resume-candidate-profile.v1",
            "candidate": {
                "display_name": "Attestation Candidate",
                "contact": {
                    "email": "candidate@example.com",
                    "phone": "312-555-0199",
                    "location": "Chicago, Illinois",
                },
            },
            "summary": "AI automation architect focused on governed workflows.",
            "skills": [
                "Python",
                "AI workflow automation",
                "data privacy",
                "efficiency measurement",
            ],
            "experience": [
                {
                    "employer": "Candidate Employer",
                    "role_title": "AI Systems Architect",
                    "dates": "2024-present",
                    "bullets": [
                        {
                            "evidence_id": "fact-automation",
                            "text": "Built Python AI workflow automation.",
                        },
                        {
                            "evidence_id": "fact-privacy",
                            "text": "Applied privacy controls to internal workflows.",
                        },
                        {
                            "evidence_id": "fact-efficiency",
                            "text": "Measured time saved from automation.",
                        },
                    ],
                }
            ],
            "education": [],
        }
        job = {
            "schema_version": "pe.resume-job-description.v1",
            "employer": "Target Employer",
            "role_title": "AI Automation Engineer",
            "description": "Build governed AI workflow automation.",
            "requirements": [
                {
                    "id": "req-automation",
                    "text": "Build Python AI workflow automation",
                    "required": True,
                },
                {
                    "id": "req-privacy",
                    "text": "Apply data privacy controls",
                    "required": True,
                },
                {
                    "id": "req-efficiency",
                    "text": "Measure time saved from automation",
                    "required": True,
                },
            ],
        }
        candidate_path = self.intake / "candidate_profile.json"
        job_path = self.intake / "job_description.json"
        self._write_json(candidate_path, candidate)
        self._write_json(job_path, job)
        self.payload = json.loads(
            (
                REPO_ROOT
                / "examples"
                / "resume"
                / "resume_tailoring_phase3_real_shadow.example.json"
            ).read_text(encoding="utf-8")
        )
        nested = self.payload["tool"]["parameters"]["resume_mission"]
        nested["candidate_source_refs"][0]["content_hash"] = self._hash(
            candidate_path
        )
        nested["target_job"]["description_ref"]["content_hash"] = self._hash(
            job_path
        )
        nested["target_job"]["employer"] = job["employer"]

    async def asyncTearDown(self) -> None:
        self.temporary.cleanup()

    async def test_real_resume_is_bound_attested_and_manifest_sealed(self) -> None:
        created = await self.service.create(self.payload)
        self.assertEqual(
            created.state,
            ResumeWorkflowState.AWAITING_USER_APPROVAL,
        )
        completed = self.service.decide(
            created.mission_id,
            ResumeDecisionRequest(
                decision="approve",
                reviewer_id="candidate-owner",
                notes="Approved for attestation validation.",
            ),
        )
        self.assertEqual(completed.state, ResumeWorkflowState.COMPLETED)
        mission_dir = self.ledger.mission_dir(created.mission_id)
        attestation_path = mission_dir / "persona-execution-attestation.json"
        attestation = json.loads(attestation_path.read_text(encoding="utf-8"))
        verification = self.ledger.verify(created.mission_id)
        persona_hash = hashlib.sha256(PERSONA_PATH.read_bytes()).hexdigest()

        self.assertEqual(
            attestation["persona_id"],
            "pe.resume_tailoring_specialist",
        )
        self.assertEqual(attestation["persona_version"], "0.1.0")
        self.assertEqual(attestation["persona_spec_sha256"], persona_hash)
        self.assertEqual(attestation["persona_model"], "Pi = <E, P, A>")
        self.assertEqual(attestation["authorization"], "AUTHORIZED")
        self.assertEqual(attestation["assessor"]["verdict"], "pass")
        self.assertTrue(attestation["user_approval_recorded"])
        self.assertTrue(attestation["ledger"]["valid"])
        self.assertEqual(
            attestation["ledger"]["terminal_hash"],
            verification["terminal_hash"],
        )
        self.assertEqual(
            attestation["resume_artifact_sha256"],
            hashlib.sha256(
                (mission_dir / "resume-final.md").read_bytes()
            ).hexdigest(),
        )
        events = self.ledger.events(created.mission_id)
        binding_event = next(
            item
            for item in events
            if item["event_type"] == "persona_binding_resolved"
        )
        self.assertEqual(
            attestation["binding_event"]["event_hash"],
            binding_event["event_hash"],
        )
        manifest = self.ledger.manifest(created.mission_id)
        artifacts = {item["path"]: item for item in manifest["artifacts"]}
        self.assertIn("persona-binding.json", artifacts)
        self.assertIn("persona-execution-attestation.json", artifacts)
        self.assertEqual(
            artifacts["persona-execution-attestation.json"]["sha256"],
            hashlib.sha256(attestation_path.read_bytes()).hexdigest(),
        )

    async def test_purge_preserves_resume_hash_and_reattests_ledger_head(self) -> None:
        created = await self.service.create(self.payload)
        self.service.decide(
            created.mission_id,
            ResumeDecisionRequest(
                decision="approve",
                reviewer_id="candidate-owner",
                notes="Approved before governed purge.",
            ),
        )
        mission_dir = self.ledger.mission_dir(created.mission_id)
        before = json.loads(
            (mission_dir / "persona-execution-attestation.json").read_text(
                encoding="utf-8"
            )
        )
        self.service.purge_sensitive(
            created.mission_id,
            ResumePurgeRequest(
                reviewer_id="candidate-owner",
                reason="Validate attestation continuity after purge.",
                confirmation="PURGE_SENSITIVE_ARTIFACTS",
            ),
        )
        after = json.loads(
            (mission_dir / "persona-execution-attestation.json").read_text(
                encoding="utf-8"
            )
        )
        verification = self.ledger.verify(created.mission_id)
        self.assertEqual(
            before["resume_artifact_sha256"],
            after["resume_artifact_sha256"],
        )
        self.assertNotEqual(
            before["ledger"]["terminal_hash"],
            after["ledger"]["terminal_hash"],
        )
        self.assertEqual(
            after["ledger"]["terminal_hash"],
            verification["terminal_hash"],
        )

    def test_runtime_contract_mismatch_fails_closed(self) -> None:
        root = Path(self.temporary.name) / "bad-registry"
        persona_dir = root / "personas"
        persona_dir.mkdir(parents=True)
        persona = json.loads(PERSONA_PATH.read_text(encoding="utf-8"))
        persona["runtime_contract"]["adapter_id"] = "untrusted-adapter"
        self._write_json(
            persona_dir / "resume_tailoring_specialist.persona.json",
            persona,
        )
        registry = ResumePersonaRegistry(
            SimpleNamespace(persona_registry_root=str(root))
        )
        with self.assertRaisesRegex(
            ResumePersonaBindingError,
            "runtime_contract.adapter_id",
        ):
            registry.resolve("pe.resume_tailoring_specialist", "0.1.0")

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
