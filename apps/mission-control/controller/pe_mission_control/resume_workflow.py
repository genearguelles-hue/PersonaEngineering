from __future__ import annotations

import hashlib
import json
import re
import tempfile
from pathlib import Path
from typing import Any
from uuid import uuid4

from .adapters.resume_tailor import ResumeTailoringAdapter
from .ledger import MissionLedger
from .models import MissionEnvelope
from .registry import AdapterRegistry
from .resume_assessor import ResumePersonaAssessor
from .resume_models import (
    ResumeDecision,
    ResumeDecisionRequest,
    ResumeWorkflowRecord,
    ResumeWorkflowState,
    utc_now,
)


class ResumeWorkflowNotFoundError(KeyError):
    pass


class ResumeWorkflowConflictError(RuntimeError):
    pass


class ResumeWorkflowService:
    """Stateful synthetic Phase 2 résumé workflow with human approval."""

    EVENT_TYPES = (
        "resume_mission_received",
        "resume_authorization_decided",
        "resume_sources_resolved",
        "resume_requirements_extracted",
        "resume_evidence_mapped",
        "resume_claim_rejected",
        "resume_draft_generated",
        "resume_assessment_completed",
        "resume_user_revision_received",
        "resume_artifact_finalized",
        "resume_ideation_chunks_prepared",
        "resume_ideation_embeddings_recorded",
        "resume_mission_terminal",
    )

    def __init__(
        self,
        registry: AdapterRegistry,
        ledger: MissionLedger,
        adapter: ResumeTailoringAdapter,
    ):
        self.registry = registry
        self.ledger = ledger
        self.adapter = adapter
        self.assessor = ResumePersonaAssessor()
        self._records: dict[str, ResumeWorkflowRecord] = {}

    async def create(self, payload: dict[str, Any]) -> ResumeWorkflowRecord:
        envelope = MissionEnvelope.model_validate(payload)
        registered = self.registry.get(envelope.tool.adapter_id)
        if registered is not self.adapter:
            raise ResumeWorkflowConflictError(
                "registered resume-tailor adapter identity mismatch"
            )
        mission_id = envelope.mission_id or f"pe-resume-{uuid4().hex[:12]}"
        if self._record_path(mission_id).exists():
            raise ResumeWorkflowConflictError(
                f"resume workflow already exists: {mission_id}"
            )
        version = envelope.persona_binding.version or "0.1.0"
        record = ResumeWorkflowRecord(
            mission_id=mission_id,
            name=envelope.name,
            persona_id=envelope.persona_binding.persona_id,
            persona_version=version,
            state=ResumeWorkflowState.RECEIVED,
            metadata={"fixture": True, "phase": 2},
        )
        self._records[mission_id] = record
        mission_dir = self.ledger.mission_dir(mission_id)
        self._write_json(mission_dir / "operator-request.json", payload)
        self._append(
            record,
            "resume_mission_received",
            {
                "adapter_id": envelope.tool.adapter_id,
                "persona_id": record.persona_id,
                "fixture": True,
                "payload_hash": self._sha256_json(payload),
            },
        )
        decision = await self.adapter.authorize(envelope)
        record.authorization_decision = decision.decision.lower()
        self._append(
            record,
            "resume_authorization_decided",
            {
                "decision": decision.decision.lower(),
                "policy_bindings": decision.policy_bindings,
                "rationale": decision.rationale,
            },
        )
        if decision.decision != "AUTHORIZED":
            record.state = ResumeWorkflowState.FAILED
            record.error = decision.rationale
            self._terminalize(record)
            return record

        record.state = ResumeWorkflowState.AUTHORIZED
        self._persist(record)
        self._run_fixture_draft(envelope, record)
        return record

    def get(self, mission_id: str) -> ResumeWorkflowRecord:
        record = self._records.get(mission_id)
        if record is None:
            path = self._record_path(mission_id)
            if path.exists():
                record = ResumeWorkflowRecord.model_validate_json(
                    path.read_text(encoding="utf-8")
                )
                self._records[mission_id] = record
        if record is None:
            raise ResumeWorkflowNotFoundError(mission_id)
        return record

    def events(self, mission_id: str) -> list[dict[str, Any]]:
        self.get(mission_id)
        return self.ledger.events(mission_id)

    def evidence(self, mission_id: str) -> dict[str, Any]:
        self.get(mission_id)
        return self.ledger.manifest(mission_id) or {
            "mission_id": mission_id,
            "sealed": False,
            "ledger": self.ledger.verify(mission_id),
            "artifacts": [],
        }

    def decide(
        self,
        mission_id: str,
        request: ResumeDecisionRequest,
    ) -> ResumeWorkflowRecord:
        record = self.get(mission_id)
        if record.state != ResumeWorkflowState.AWAITING_USER_APPROVAL:
            raise ResumeWorkflowConflictError(
                "workflow is not awaiting user approval"
            )
        if request.decision == ResumeDecision.REVISE:
            self._receive_revision(record, request)
            return record
        self._approve(record, request)
        return record

    def _run_fixture_draft(
        self,
        envelope: MissionEnvelope,
        record: ResumeWorkflowRecord,
        corrections: list[str] | None = None,
    ) -> None:
        record.state = ResumeWorkflowState.DRAFTING
        nested = envelope.tool.parameters["resume_mission"]
        mission_dir = self.ledger.mission_dir(record.mission_id)
        sources = [
            {
                "source_id": "synthetic-career-profile",
                "hash": "a" * 64,
                "classification": "synthetic_non_personal",
            },
            {
                "source_id": "synthetic-job-description",
                "hash": "b" * 64,
                "classification": "synthetic_non_personal",
            },
        ]
        self._write_json(mission_dir / "resolved-sources.json", {"sources": sources})
        self._append(
            record,
            "resume_sources_resolved",
            {"source_count": len(sources), "artifact": "resolved-sources.json"},
        )

        requirements = [
            {"id": "req-1", "text": "AI-assisted workflow automation"},
            {"id": "req-2", "text": "data privacy and confidentiality"},
            {"id": "req-3", "text": "efficiency measurement"},
        ]
        self._write_json(
            mission_dir / "requirements.json", {"requirements": requirements}
        )
        self._append(
            record,
            "resume_requirements_extracted",
            {"requirement_count": len(requirements), "artifact": "requirements.json"},
        )

        evidence_map = [
            {
                "requirement_id": "req-1",
                "supporting_evidence_ids": ["fact-persona-engineering"],
            },
            {
                "requirement_id": "req-2",
                "supporting_evidence_ids": ["fact-governed-evidence"],
            },
            {
                "requirement_id": "req-3",
                "supporting_evidence_ids": ["fact-token-telemetry"],
            },
        ]
        self._write_json(
            mission_dir / "evidence-map.json", {"mappings": evidence_map}
        )
        self._append(
            record,
            "resume_evidence_mapped",
            {
                "mapping_count": len(evidence_map),
                "artifact": "evidence-map.json",
            },
        )

        rejected_claims = [
            {
                "claim_id": "claim-unsupported-1",
                "claim_hash": hashlib.sha256(
                    b"Administered production Kubernetes clusters"
                ).hexdigest(),
                "reason": "no authorized supporting source",
                "removed_from_draft": True,
            }
        ]
        self._write_json(
            mission_dir / "rejected-claims.json",
            {"rejected_claims": rejected_claims},
        )
        self._append(
            record,
            "resume_claim_rejected",
            {
                "claim_id": rejected_claims[0]["claim_id"],
                "claim_hash": rejected_claims[0]["claim_hash"],
                "reason": rejected_claims[0]["reason"],
            },
        )

        correction_lines = corrections or []
        correction_section = ""
        if correction_lines:
            correction_section = "\n\nPositioning corrections:\n" + "\n".join(
                f"- {item}" for item in correction_lines
            )
        role = nested["target_job"]["role_title"]
        draft = (
            f"# Synthetic Candidate\n\n"
            f"Target role: {role}\n\n"
            "## Professional Summary\n\n"
            "AI systems architect focused on evidence-bounded workflow "
            "automation, behavioral governance, privacy controls, and "
            "measurable operational efficiency.\n\n"
            "## Selected Evidence\n\n"
            "- Designed Persona Engineering governance patterns for "
            "mission authorization, assessment, and provenance.\n"
            "- Integrated governed Selenium and JMeter evidence workflows.\n"
            "- Defined token telemetry and efficiency measurement controls."
            f"{correction_section}\n"
        )
        draft_path = mission_dir / "resume-draft.md"
        draft_path.write_text(draft, encoding="utf-8")
        self._append(
            record,
            "resume_draft_generated",
            {
                "artifact": "resume-draft.md",
                "sha256": self._file_hash(draft_path),
                "revision": record.revision_count,
            },
        )

        minimum_coverage = float(
            nested["governance"].get("minimum_requirement_coverage", 0.75)
        )
        assessment = self.assessor.assess(
            evidence_map=evidence_map,
            rejected_claims=rejected_claims,
            draft=draft,
            minimum_coverage=minimum_coverage,
        )
        self._write_json(
            mission_dir / f"assessment-r{record.revision_count}.json",
            assessment.model_dump(mode="json"),
        )
        record.assessor_verdict = assessment.verdict
        self._append(
            record,
            "resume_assessment_completed",
            {
                "assessor_id": assessment.assessor_id,
                "verdict": assessment.verdict,
                "requirement_coverage": assessment.requirement_coverage,
                "unsupported_claim_count": assessment.unsupported_claim_count,
                "privacy_finding_count": len(assessment.privacy_findings),
                "artifact": f"assessment-r{record.revision_count}.json",
            },
        )
        if assessment.verdict != "pass":
            record.state = ResumeWorkflowState.FAILED
            record.error = "synthetic draft did not pass independent assessment"
            self._terminalize(record)
            return
        record.state = ResumeWorkflowState.AWAITING_USER_APPROVAL
        record.updated_at = utc_now()
        self._persist(record)

    def _receive_revision(
        self,
        record: ResumeWorkflowRecord,
        request: ResumeDecisionRequest,
    ) -> None:
        self._reject_pii(request.corrections)
        record.revision_count += 1
        mission_dir = self.ledger.mission_dir(record.mission_id)
        revision = {
            "schema_version": "pe.resume-user-revision.v1",
            "reviewer_id": request.reviewer_id,
            "notes": request.notes,
            "corrections": request.corrections,
            "revision": record.revision_count,
            "received_at": utc_now().isoformat(),
        }
        revision_path = mission_dir / f"user-revision-r{record.revision_count}.json"
        self._write_json(revision_path, revision)
        self._append(
            record,
            "resume_user_revision_received",
            {
                "reviewer_id": request.reviewer_id,
                "revision": record.revision_count,
                "correction_count": len(request.corrections),
                "artifact": revision_path.name,
                "payload_hash": self._sha256_json(revision),
            },
        )
        operator_request = json.loads(
            (mission_dir / "operator-request.json").read_text(encoding="utf-8")
        )
        envelope = MissionEnvelope.model_validate(operator_request)
        self._run_fixture_draft(
            envelope,
            record,
            corrections=request.corrections,
        )

    def _approve(
        self,
        record: ResumeWorkflowRecord,
        request: ResumeDecisionRequest,
    ) -> None:
        if record.assessor_verdict != "pass":
            raise ResumeWorkflowConflictError(
                "user approval cannot override a non-passing Assessor verdict"
            )
        mission_dir = self.ledger.mission_dir(record.mission_id)
        draft_path = mission_dir / "resume-draft.md"
        final_path = mission_dir / "resume-final.md"
        final_path.write_bytes(draft_path.read_bytes())
        record.final_artifact = final_path.name
        self._append(
            record,
            "resume_artifact_finalized",
            {
                "artifact": final_path.name,
                "sha256": self._file_hash(final_path),
                "approved_by": request.reviewer_id,
                "approval_notes_hash": hashlib.sha256(
                    request.notes.encode("utf-8")
                ).hexdigest(),
            },
        )

        chunks = self._prepare_sanitized_chunks(record)
        chunks_path = mission_dir / "ideation-chunks.sanitized.json"
        self._write_json(chunks_path, {"chunks": chunks})
        self._append(
            record,
            "resume_ideation_chunks_prepared",
            {
                "policy_id": "pe.resume_ideation_ingestion.v1",
                "eligible_chunk_count": len(chunks),
                "excluded_chunk_count": 1,
                "artifact": chunks_path.name,
                "privacy_transform_version": "resume-synthetic-redactor:0.1.0",
            },
        )

        embedding_manifest = self._embed_chunks(record, chunks)
        manifest_path = mission_dir / "ideation-embedding-manifest.json"
        self._write_json(manifest_path, embedding_manifest)
        record.ideation_manifest = manifest_path.name
        self._append(
            record,
            "resume_ideation_embeddings_recorded",
            {
                "policy_id": "pe.resume_ideation_ingestion.v1",
                "embedding_model_id": embedding_manifest["embedding_model_id"],
                "embedded_chunk_ids": [
                    item["chunk_id"] for item in embedding_manifest["embeddings"]
                ],
                "excluded_chunk_ids": ["claim-unsupported-1"],
                "exclusion_reasons": {
                    "claim-unsupported-1": "negative evidence kept out of positive vectors"
                },
                "vector_collection": embedding_manifest["vector_collection"],
                "embedding_manifest_hash": self._sha256_json(embedding_manifest),
                "artifact": manifest_path.name,
            },
        )
        record.state = ResumeWorkflowState.COMPLETED
        self._terminalize(record)

    def _terminalize(self, record: ResumeWorkflowRecord) -> None:
        preterminal = self.ledger.verify(record.mission_id)
        self._append(
            record,
            "resume_mission_terminal",
            {
                "terminal_state": record.state,
                "assessor_verdict": record.assessor_verdict,
                "preterminal_ledger_valid": preterminal["valid"],
                "revision_count": record.revision_count,
            },
        )
        record.updated_at = utc_now()
        self._persist(record)
        final_verification = self.ledger.verify(record.mission_id)
        if not final_verification["valid"]:
            raise ResumeWorkflowConflictError(
                "ledger verification failed before evidence sealing"
            )
        self.ledger.seal_manifest(record.mission_id)

    def _prepare_sanitized_chunks(
        self, record: ResumeWorkflowRecord
    ) -> list[dict[str, Any]]:
        raw_chunks = [
            {
                "chunk_id": f"{record.mission_id}-verified-governance",
                "type": "candidate_verified_fact",
                "text": (
                    "Designed behavioral-governance patterns for mission "
                    "authorization, independent assessment, and provenance."
                ),
            },
            {
                "chunk_id": f"{record.mission_id}-requirement-map",
                "type": "requirement_evidence_mapping",
                "text": (
                    "Mapped AI workflow automation, confidentiality controls, "
                    "and efficiency measurement to authorized synthetic evidence."
                ),
            },
            {
                "chunk_id": f"{record.mission_id}-preference",
                "type": "user_positioning_preference",
                "text": (
                    "Prefer evidence-bounded positioning that joins AI "
                    "automation with behavioral governance."
                ),
            },
        ]
        for item in raw_chunks:
            self._reject_pii([item["text"]])
            item.update(
                {
                    "mission_id": record.mission_id,
                    "persona_id": record.persona_id,
                    "persona_version": record.persona_version,
                    "assessor_verdict": record.assessor_verdict,
                    "privacy_transform_version": "resume-synthetic-redactor:0.1.0",
                    "source_hashes": ["a" * 64, "b" * 64],
                }
            )
        return raw_chunks

    @staticmethod
    def _embed_chunks(
        record: ResumeWorkflowRecord,
        chunks: list[dict[str, Any]],
    ) -> dict[str, Any]:
        embeddings = []
        for item in chunks:
            digest = hashlib.sha256(item["text"].encode("utf-8")).digest()
            vector = [
                round((int.from_bytes(digest[i : i + 2], "big") / 32767.5) - 1, 6)
                for i in range(0, 16, 2)
            ]
            embeddings.append(
                {
                    "chunk_id": item["chunk_id"],
                    "vector": vector,
                    "dimensions": len(vector),
                }
            )
        return {
            "schema_version": "pe.resume-embedding-manifest.v1",
            "mission_id": record.mission_id,
            "embedding_model_id": "fixture-deterministic-sha256-8d:0.1.0",
            "vector_collection": "resume_tailoring_phase2_synthetic",
            "production_vector_write": False,
            "embeddings": embeddings,
        }

    @staticmethod
    def _reject_pii(values: list[str]) -> None:
        patterns = (
            re.compile(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}"),
            re.compile(r"\b\d{3}[-.\s]\d{3}[-.\s]\d{4}\b"),
            re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
            re.compile(r"\b(?:api[_-]?key|bearer|token)\b", re.IGNORECASE),
        )
        for value in values:
            if any(pattern.search(value) for pattern in patterns):
                raise ResumeWorkflowConflictError(
                    "Phase 2 synthetic workflow rejected possible PII or secret data"
                )

    def _append(
        self,
        record: ResumeWorkflowRecord,
        event_type: str,
        details: dict[str, Any],
    ) -> None:
        if event_type not in self.EVENT_TYPES:
            raise ResumeWorkflowConflictError(
                f"unregistered résumé ledger event: {event_type}"
            )
        self.ledger.append(
            record.mission_id,
            event_type,
            record.state,
            details,
        )
        record.updated_at = utc_now()
        self._persist(record)

    def _record_path(self, mission_id: str) -> Path:
        return self.ledger.missions_dir / mission_id / "resume-workflow-record.json"

    def _persist(self, record: ResumeWorkflowRecord) -> None:
        self._write_json(
            self.ledger.mission_dir(record.mission_id)
            / "resume-workflow-record.json",
            record.model_dump(mode="json"),
        )

    @staticmethod
    def _write_json(path: Path, value: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            delete=False,
        ) as handle:
            json.dump(value, handle, indent=2, sort_keys=True)
            handle.write("\n")
            temporary = Path(handle.name)
        try:
            temporary.replace(path)
        finally:
            temporary.unlink(missing_ok=True)

    @staticmethod
    def _sha256_json(value: dict[str, Any]) -> str:
        encoded = json.dumps(
            value, sort_keys=True, separators=(",", ":"), default=str
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    @staticmethod
    def _file_hash(path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()
