from __future__ import annotations

import hashlib
import json
import re
import tempfile
from datetime import timedelta
from pathlib import Path
from typing import Any
from uuid import uuid4

from .adapters.resume_tailor import ResumeTailoringAdapter
from .ledger import MissionLedger
from .models import MissionEnvelope
from .registry import AdapterRegistry
from .resume_assessor import ResumePersonaAssessor
from .resume_attestation import (
    ResolvedResumePersona,
    ResumePersonaBindingError,
    ResumePersonaRegistry,
)
from .resume_models import (
    ResumeDecision,
    ResumeDecisionRequest,
    ResumePurgeRequest,
    ResumeWorkflowRecord,
    ResumeWorkflowState,
    utc_now,
)
from .resume_privacy import ResumePrivacyError, ResumePrivacyTransformer
from .resume_sources import (
    ResolvedResumeSources,
    ResumeSourceError,
    ResumeSourceResolver,
)


class ResumeWorkflowNotFoundError(KeyError):
    pass


class ResumeWorkflowConflictError(RuntimeError):
    pass


class ResumeWorkflowService:
    """Governed synthetic and local real-data shadow résumé workflow."""

    EVENT_TYPES = (
        "resume_mission_received",
        "persona_binding_resolved",
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
    OPTIONAL_EVENT_TYPES = ("resume_sensitive_artifacts_purged",)

    STOPWORDS = {
        "a",
        "an",
        "and",
        "are",
        "as",
        "at",
        "be",
        "by",
        "for",
        "from",
        "in",
        "is",
        "of",
        "on",
        "or",
        "that",
        "the",
        "to",
        "with",
        "will",
    }

    def __init__(
        self,
        registry: AdapterRegistry,
        ledger: MissionLedger,
        adapter: ResumeTailoringAdapter,
    ):
        self.registry = registry
        self.ledger = ledger
        self.adapter = adapter
        self.privacy = ResumePrivacyTransformer()
        self.resolver = ResumeSourceResolver(adapter.settings, self.privacy)
        self.persona_registry = ResumePersonaRegistry(adapter.settings)
        self.assessor = ResumePersonaAssessor(self.privacy)
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
        fixture = envelope.tool.parameters.get("fixture") is True
        version = envelope.persona_binding.version or "0.1.0"
        record = ResumeWorkflowRecord(
            mission_id=mission_id,
            name=envelope.name,
            persona_id=envelope.persona_binding.persona_id,
            persona_version=version,
            state=ResumeWorkflowState.RECEIVED,
            metadata={
                "fixture": fixture,
                "phase": 2 if fixture else 3,
                "processing_mode": "synthetic" if fixture else "real_shadow",
            },
        )
        self._records[mission_id] = record
        if not fixture:
            self._reject_inline_real_source_content(envelope)
        mission_dir = self.ledger.mission_dir(mission_id)
        self._write_json(mission_dir / "operator-request.json", payload)
        self._append(
            record,
            "resume_mission_received",
            {
                "adapter_id": envelope.tool.adapter_id,
                "persona_id": record.persona_id,
                "fixture": fixture,
                "processing_mode": record.metadata["processing_mode"],
                "payload_hash": self._sha256_json(payload),
            },
        )
        try:
            self._resolve_persona_binding(record)
        except ResumePersonaBindingError as exc:
            record.authorization_decision = "blocked"
            record.state = ResumeWorkflowState.FAILED
            record.error = str(exc)
            self._append(
                record,
                "resume_authorization_decided",
                {
                    "decision": "blocked",
                    "policy_bindings": ["PE-RESUME-PERSONA-BINDING"],
                    "rationale": str(exc),
                },
            )
            self._terminalize(record)
            return record
        decision = await self.adapter.authorize(envelope)
        record.authorization_decision = decision.decision.lower()
        authorization_details = {
            "decision": decision.decision.lower(),
            "policy_bindings": decision.policy_bindings,
            "rationale": decision.rationale,
        }
        if not fixture:
            controls = envelope.tool.parameters["resume_mission"].get(
                "real_data_controls", {}
            )
            authorization_details.update(
                {
                    "consent_record_hash": hashlib.sha256(
                        str(controls.get("consent_record_id", "")).encode("utf-8")
                    ).hexdigest(),
                    "purpose": controls.get("purpose"),
                    "processing_mode": controls.get("processing_mode"),
                    "retention_hours": controls.get("retention_hours"),
                }
            )
        self._append(
            record,
            "resume_authorization_decided",
            authorization_details,
        )
        if decision.decision != "AUTHORIZED":
            record.state = ResumeWorkflowState.FAILED
            record.error = decision.rationale
            self._terminalize(record)
            return record

        record.state = ResumeWorkflowState.AUTHORIZED
        self._persist(record)
        try:
            if fixture:
                self._run_fixture_draft(envelope, record)
            else:
                self._run_real_shadow_draft(envelope, record)
        except (ResumeSourceError, ResumePrivacyError, ValueError) as exc:
            self._fail(record, str(exc))
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
        review_states = {
            ResumeWorkflowState.AWAITING_USER_APPROVAL,
            ResumeWorkflowState.AWAITING_USER_REVISION,
        }
        if record.state not in review_states:
            raise ResumeWorkflowConflictError(
                "workflow is not awaiting user review"
            )
        if request.decision == ResumeDecision.REVISE:
            self._receive_revision(record, request)
            return record
        self._approve(record, request)
        return record

    def purge_sensitive(
        self,
        mission_id: str,
        request: ResumePurgeRequest,
    ) -> dict[str, Any]:
        record = self.get(mission_id)
        if record.metadata.get("fixture") is not False:
            raise ResumeWorkflowConflictError(
                "sensitive-artifact purge is for real-data missions only"
            )
        if record.state not in {
            ResumeWorkflowState.COMPLETED,
            ResumeWorkflowState.FAILED,
        }:
            raise ResumeWorkflowConflictError(
                "sensitive artifacts may be purged only after terminal state"
            )
        if record.metadata.get("sensitive_artifacts_purged_at"):
            raise ResumeWorkflowConflictError(
                "sensitive artifacts were already purged"
            )
        mission_dir = self.ledger.mission_dir(mission_id)
        candidates = [
            mission_dir / "requirements.json",
            mission_dir / "evidence-map.json",
            mission_dir / "resume-draft.md",
            mission_dir / "resume-final.md",
            mission_dir / "ideation-chunks.pending.sanitized.json",
        ]
        candidates.extend(sorted(mission_dir.glob("user-revision-r*.json")))
        removed: list[dict[str, Any]] = []
        for path in candidates:
            if not path.is_file():
                continue
            removed.append(
                {
                    "path_hash": hashlib.sha256(path.name.encode("utf-8")).hexdigest(),
                    "content_hash": self._file_hash(path),
                    "size_bytes": path.stat().st_size,
                }
            )
            path.unlink()
        purge_time = utc_now()
        record.final_artifact = None
        record.metadata["sensitive_artifacts_purged_at"] = purge_time.isoformat()
        receipt = {
            "schema_version": "pe.resume-sensitive-purge-receipt.v1",
            "mission_id": mission_id,
            "purged_at": purge_time.isoformat(),
            "reviewer_id_hash": hashlib.sha256(
                request.reviewer_id.encode("utf-8")
            ).hexdigest(),
            "reason_hash": hashlib.sha256(
                request.reason.encode("utf-8")
            ).hexdigest(),
            "removed_artifact_count": len(removed),
            "removed_artifacts": removed,
            "source_files_deleted": False,
        }
        self._write_json(mission_dir / "sensitive-purge-receipt.json", receipt)
        self._append(
            record,
            "resume_sensitive_artifacts_purged",
            {
                "removed_artifact_count": len(removed),
                "receipt_hash": self._sha256_json(receipt),
                "source_files_deleted": False,
            },
        )
        if not self.ledger.verify(mission_id)["valid"]:
            raise ResumeWorkflowConflictError(
                "ledger verification failed after sensitive-artifact purge"
            )
        verification = self.ledger.verify(mission_id)
        self._write_execution_attestation(record, verification)
        self._persist(record)
        self.ledger.seal_manifest(mission_id)
        return receipt

    def _resolve_persona_binding(
        self,
        record: ResumeWorkflowRecord,
    ) -> ResolvedResumePersona:
        resolved = self.persona_registry.resolve(
            record.persona_id,
            record.persona_version,
        )
        mission_dir = self.ledger.mission_dir(record.mission_id)
        binding_path = mission_dir / "persona-binding.json"
        self._write_json(binding_path, resolved.artifact())
        binding_event = self._append(
            record,
            "persona_binding_resolved",
            resolved.ledger_details(self._file_hash(binding_path)),
        )
        record.metadata["persona_binding"] = {
            "persona_spec_sha256": resolved.persona_spec_sha256,
            "runtime_contract_sha256": resolved.runtime_contract_sha256,
            "persona_model": resolved.persona_model,
            "engram_ids": list(resolved.engram_ids),
            "primitive_ids": list(resolved.primitive_ids),
            "axiom_ids": list(resolved.axiom_ids),
            "binding_event_sequence": binding_event["sequence"],
            "binding_event_hash": binding_event["event_hash"],
            "registry_index_verified": resolved.registry_index_verified,
        }
        self._persist(record)
        return resolved

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
        self._write_draft_and_assess(
            record=record,
            nested=nested,
            draft=draft,
            evidence_map=evidence_map,
            rejected_claims=rejected_claims,
            allow_contact_pii=False,
            failure_message="synthetic draft did not pass independent assessment",
        )

    def _run_real_shadow_draft(
        self,
        envelope: MissionEnvelope,
        record: ResumeWorkflowRecord,
        corrections: list[str] | None = None,
    ) -> None:
        record.state = ResumeWorkflowState.DRAFTING
        nested = envelope.tool.parameters["resume_mission"]
        mission_dir = self.ledger.mission_dir(record.mission_id)
        resolved = self.resolver.resolve(nested)
        source_metadata = [
            resolved.candidate.ledger_metadata(),
            resolved.job.ledger_metadata(),
        ]
        self._write_json(
            mission_dir / "resolved-sources.json",
            {
                "schema_version": "pe.resume-resolved-sources.v2",
                "sources": source_metadata,
                "raw_content_persisted": False,
            },
        )
        self._append(
            record,
            "resume_sources_resolved",
            {
                "source_count": len(source_metadata),
                "artifact": "resolved-sources.json",
                "source_hashes": resolved.source_hashes,
                "raw_content_in_ledger": False,
                "blocked_privacy_finding_count": 0,
            },
        )

        requirements = self._requirements(resolved.job.document)
        self._write_json(
            mission_dir / "requirements.json",
            {
                "schema_version": "pe.resume-requirements.v2",
                "requirements": requirements,
                "sensitive_artifact": True,
            },
        )
        self._append(
            record,
            "resume_requirements_extracted",
            {
                "requirement_count": len(requirements),
                "required_count": sum(
                    1 for item in requirements if item["required"]
                ),
                "artifact": "requirements.json",
                "artifact_hash": self._file_hash(
                    mission_dir / "requirements.json"
                ),
            },
        )

        evidence_catalog = self._evidence_catalog(resolved.candidate.document)
        emphasis = list(corrections or [])
        evidence_map = self._map_evidence(
            requirements,
            evidence_catalog,
            emphasis=emphasis,
        )
        self._write_json(
            mission_dir / "evidence-map.json",
            {
                "schema_version": "pe.resume-evidence-map.v2",
                "mappings": evidence_map,
                "sensitive_artifact": True,
            },
        )
        supported_count = sum(
            1 for item in evidence_map if item["supporting_evidence_ids"]
        )
        self._append(
            record,
            "resume_evidence_mapped",
            {
                "mapping_count": len(evidence_map),
                "supported_mapping_count": supported_count,
                "artifact": "evidence-map.json",
                "artifact_hash": self._file_hash(mission_dir / "evidence-map.json"),
            },
        )

        rejected_claims: list[dict[str, Any]] = []
        self._write_json(
            mission_dir / "rejected-claims.json",
            {"rejected_claims": rejected_claims},
        )
        self._append(
            record,
            "resume_claim_rejected",
            {
                "rejected_claim_count": 0,
                "generation_strategy": "source-preserving_selection_only",
            },
        )

        draft = self._build_real_draft(
            resolved,
            evidence_catalog,
            emphasis=emphasis,
        )
        chunks = self._prepare_real_sanitized_chunks(
            record,
            nested,
            resolved,
            evidence_map,
            emphasis=emphasis,
        )
        self._write_json(
            mission_dir / "ideation-chunks.pending.sanitized.json",
            {
                "schema_version": "pe.resume-sanitized-chunks.v2",
                "chunks": chunks,
                "production_vector_write": False,
                "approval_pending": True,
            },
        )
        self._write_draft_and_assess(
            record=record,
            nested=nested,
            draft=draft,
            evidence_map=evidence_map,
            rejected_claims=rejected_claims,
            allow_contact_pii=True,
            failure_message="real-data shadow draft requires revision",
            fail_terminal=False,
        )

    def _write_draft_and_assess(
        self,
        *,
        record: ResumeWorkflowRecord,
        nested: dict[str, Any],
        draft: str,
        evidence_map: list[dict[str, Any]],
        rejected_claims: list[dict[str, Any]],
        allow_contact_pii: bool,
        failure_message: str,
        fail_terminal: bool = True,
    ) -> None:
        mission_dir = self.ledger.mission_dir(record.mission_id)
        draft_path = mission_dir / "resume-draft.md"
        draft_path.write_text(draft, encoding="utf-8")
        self._append(
            record,
            "resume_draft_generated",
            {
                "artifact": "resume-draft.md",
                "sha256": self._file_hash(draft_path),
                "revision": record.revision_count,
                "contains_authorized_contact_pii": allow_contact_pii,
                "external_model_calls": False,
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
            allow_contact_pii=allow_contact_pii,
        )
        assessment_path = (
            mission_dir / f"assessment-r{record.revision_count}.json"
        )
        self._write_json(
            assessment_path,
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
                "artifact": assessment_path.name,
            },
        )
        if assessment.verdict != "pass":
            if fail_terminal:
                record.state = ResumeWorkflowState.FAILED
                record.error = failure_message
                self._terminalize(record)
            else:
                record.state = ResumeWorkflowState.AWAITING_USER_REVISION
                record.error = failure_message
                record.updated_at = utc_now()
                self._persist(record)
            return
        record.error = None
        record.state = ResumeWorkflowState.AWAITING_USER_APPROVAL
        record.updated_at = utc_now()
        self._persist(record)

    def _receive_revision(
        self,
        record: ResumeWorkflowRecord,
        request: ResumeDecisionRequest,
    ) -> None:
        try:
            if record.metadata.get("fixture"):
                self._reject_pii(request.corrections)
            else:
                self.privacy.scan_revision(request.corrections)
        except ResumePrivacyError as exc:
            raise ResumeWorkflowConflictError(str(exc)) from exc
        record.revision_count += 1
        mission_dir = self.ledger.mission_dir(record.mission_id)
        revision = {
            "schema_version": "pe.resume-user-revision.v1",
            "reviewer_id": request.reviewer_id,
            "notes": request.notes,
            "corrections": request.corrections,
            "revision": record.revision_count,
            "received_at": utc_now().isoformat(),
            "sensitive_artifact": not record.metadata.get("fixture"),
        }
        revision_path = mission_dir / f"user-revision-r{record.revision_count}.json"
        self._write_json(revision_path, revision)
        self._append(
            record,
            "resume_user_revision_received",
            {
                "reviewer_id_hash": hashlib.sha256(
                    request.reviewer_id.encode("utf-8")
                ).hexdigest(),
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
        try:
            if record.metadata.get("fixture"):
                self._run_fixture_draft(
                    envelope,
                    record,
                    corrections=request.corrections,
                )
            else:
                self._run_real_shadow_draft(
                    envelope,
                    record,
                    corrections=request.corrections,
                )
        except (ResumeSourceError, ResumePrivacyError, ValueError) as exc:
            self._fail(record, str(exc))

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
        record.metadata["final_artifact_sha256"] = self._file_hash(final_path)
        self._append(
            record,
            "resume_artifact_finalized",
            {
                "artifact": final_path.name,
                "sha256": self._file_hash(final_path),
                "approved_by_hash": hashlib.sha256(
                    request.reviewer_id.encode("utf-8")
                ).hexdigest(),
                "approval_notes_hash": hashlib.sha256(
                    request.notes.encode("utf-8")
                ).hexdigest(),
                "external_submission_performed": False,
            },
        )

        if record.metadata.get("fixture"):
            chunks = self._prepare_fixture_sanitized_chunks(record)
            privacy_version = "resume-synthetic-redactor:0.1.0"
            excluded_count = 1
        else:
            pending = json.loads(
                (
                    mission_dir / "ideation-chunks.pending.sanitized.json"
                ).read_text(encoding="utf-8")
            )
            chunks = pending["chunks"]
            privacy_version = self.privacy.version
            excluded_count = 0
        chunks_path = mission_dir / "ideation-chunks.sanitized.json"
        self._write_json(
            chunks_path,
            {
                "schema_version": "pe.resume-sanitized-chunks.v2",
                "chunks": chunks,
                "production_vector_write": False,
                "approval_pending": False,
            },
        )
        self._append(
            record,
            "resume_ideation_chunks_prepared",
            {
                "policy_id": "pe.resume_ideation_ingestion.v1",
                "eligible_chunk_count": len(chunks),
                "excluded_chunk_count": excluded_count,
                "artifact": chunks_path.name,
                "privacy_transform_version": privacy_version,
                "raw_candidate_content_in_chunks": False,
            },
        )

        embedding_manifest = self._embed_chunks(
            record,
            chunks,
            fixture=bool(record.metadata.get("fixture")),
        )
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
                "excluded_chunk_ids": (
                    ["claim-unsupported-1"]
                    if record.metadata.get("fixture")
                    else []
                ),
                "exclusion_reasons": (
                    {
                        "claim-unsupported-1": (
                            "negative evidence kept out of positive vectors"
                        )
                    }
                    if record.metadata.get("fixture")
                    else {}
                ),
                "vector_collection": embedding_manifest["vector_collection"],
                "embedding_manifest_hash": self._sha256_json(embedding_manifest),
                "artifact": manifest_path.name,
                "production_vector_write": False,
            },
        )
        if not record.metadata.get("fixture"):
            self._write_retention_manifest(record)
        record.state = ResumeWorkflowState.COMPLETED
        self._terminalize(record)

    def _write_retention_manifest(self, record: ResumeWorkflowRecord) -> None:
        mission_dir = self.ledger.mission_dir(record.mission_id)
        operator_request = json.loads(
            (mission_dir / "operator-request.json").read_text(encoding="utf-8")
        )
        controls = operator_request["tool"]["parameters"]["resume_mission"][
            "real_data_controls"
        ]
        retention_hours = int(controls["retention_hours"])
        finalized_at = utc_now()
        manifest = {
            "schema_version": "pe.resume-retention-manifest.v1",
            "mission_id": record.mission_id,
            "retention_hours": retention_hours,
            "purge_due_at": (
                finalized_at + timedelta(hours=retention_hours)
            ).isoformat(),
            "purge_requires_confirmation": True,
            "purge_endpoint": (
                f"/api/v1/resume-workflows/{record.mission_id}/purge-sensitive"
            ),
            "sensitive_artifact_patterns": [
                "requirements.json",
                "evidence-map.json",
                "resume-draft.md",
                "resume-final.md",
                "user-revision-r*.json",
                "ideation-chunks.pending.sanitized.json",
            ],
            "source_files_owned_by_runtime": False,
            "automatic_external_submission": False,
        }
        self._write_json(mission_dir / "retention-manifest.json", manifest)
        record.metadata["purge_due_at"] = manifest["purge_due_at"]

    def _terminalize(self, record: ResumeWorkflowRecord) -> None:
        preterminal = self.ledger.verify(record.mission_id)
        terminal_event = self._append(
            record,
            "resume_mission_terminal",
            {
                "terminal_state": record.state,
                "assessor_verdict": record.assessor_verdict,
                "preterminal_ledger_valid": preterminal["valid"],
                "revision_count": record.revision_count,
                "processing_mode": record.metadata.get("processing_mode"),
            },
        )
        record.metadata["mission_terminal_event_hash"] = terminal_event["event_hash"]
        record.updated_at = utc_now()
        self._persist(record)
        final_verification = self.ledger.verify(record.mission_id)
        if not final_verification["valid"]:
            raise ResumeWorkflowConflictError(
                "ledger verification failed before evidence sealing"
            )
        if "persona_binding" in record.metadata:
            self._write_execution_attestation(record, final_verification)
            self._persist(record)
        self.ledger.seal_manifest(record.mission_id)

    def _write_execution_attestation(
        self,
        record: ResumeWorkflowRecord,
        ledger_verification: dict[str, Any],
    ) -> None:
        binding = record.metadata.get("persona_binding")
        if not isinstance(binding, dict):
            raise ResumeWorkflowConflictError(
                "persona execution cannot be attested without a resolved binding"
            )
        terminal_event_hash = record.metadata.get("mission_terminal_event_hash")
        if not isinstance(terminal_event_hash, str):
            raise ResumeWorkflowConflictError(
                "persona execution cannot be attested without a terminal event"
            )
        attestation = {
            "schema_version": "pe.resume-persona-execution-attestation.v1",
            "mission_id": record.mission_id,
            "persona_id": record.persona_id,
            "persona_version": record.persona_version,
            "persona_spec_sha256": binding["persona_spec_sha256"],
            "persona_model": binding["persona_model"],
            "runtime_contract_sha256": binding["runtime_contract_sha256"],
            "active_components": {
                "engram_ids": binding["engram_ids"],
                "primitive_ids": binding["primitive_ids"],
                "axiom_ids": binding["axiom_ids"],
            },
            "binding_event": {
                "sequence": binding["binding_event_sequence"],
                "event_hash": binding["binding_event_hash"],
            },
            "authorization": (
                record.authorization_decision.upper()
                if record.authorization_decision
                else "UNKNOWN"
            ),
            "assessor": {
                "assessor_id": "resume-persona-assessor@0.1.0",
                "verdict": record.assessor_verdict,
            },
            "user_approval_recorded": bool(
                record.metadata.get("final_artifact_sha256")
            ),
            "ledger": {
                "valid": ledger_verification["valid"],
                "event_count": ledger_verification["event_count"],
                "terminal_hash": ledger_verification["terminal_hash"],
                "mission_terminal_event_hash": terminal_event_hash,
            },
            "resume_artifact_sha256": record.metadata.get(
                "final_artifact_sha256"
            ),
            "attested_at": utc_now().isoformat(),
        }
        attestation_path = (
            self.ledger.mission_dir(record.mission_id)
            / "persona-execution-attestation.json"
        )
        self._write_json(attestation_path, attestation)
        record.metadata["persona_execution_attestation"] = {
            "artifact": attestation_path.name,
            "sha256": self._file_hash(attestation_path),
            "ledger_terminal_hash": ledger_verification["terminal_hash"],
        }

    def _fail(self, record: ResumeWorkflowRecord, message: str) -> None:
        record.state = ResumeWorkflowState.FAILED
        record.error = message
        self._terminalize(record)

    def _prepare_fixture_sanitized_chunks(
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

    def _prepare_real_sanitized_chunks(
        self,
        record: ResumeWorkflowRecord,
        nested: dict[str, Any],
        resolved: ResolvedResumeSources,
        evidence_map: list[dict[str, Any]],
        *,
        emphasis: list[str],
    ) -> list[dict[str, Any]]:
        profile = resolved.candidate.document
        job = resolved.job.document
        candidate = profile["candidate"]
        explicit = [
            candidate.get("display_name", ""),
            job.get("employer", ""),
            nested.get("target_job", {}).get("employer", ""),
        ]
        contact = candidate.get("contact", {})
        if isinstance(contact, dict):
            explicit.extend(str(value) for value in contact.values())
        for experience in profile.get("experience", []):
            if isinstance(experience, dict):
                explicit.append(str(experience.get("employer", "")))

        chunks: list[dict[str, Any]] = []
        for mapping in evidence_map:
            evidence = mapping.get("supporting_evidence", [])
            if not evidence:
                continue
            combined = " ".join(
                str(item.get("text", ""))
                for item in evidence
                if isinstance(item, dict)
            )
            sanitized = self.privacy.sanitize(
                (
                    f"Requirement {mapping['requirement_text']} is supported by "
                    f"verified candidate evidence: {combined}"
                ),
                explicit_values=explicit,
            )
            chunks.append(
                {
                    "chunk_id": (
                        f"{record.mission_id}-mapping-{mapping['requirement_id']}"
                    ),
                    "type": "requirement_evidence_mapping",
                    "text": sanitized,
                    "mission_id": record.mission_id,
                    "persona_id": record.persona_id,
                    "persona_version": record.persona_version,
                    "assessor_verdict": record.assessor_verdict,
                    "privacy_transform_version": self.privacy.version,
                    "source_hashes": resolved.source_hashes,
                }
            )
        positioning = nested.get("strategy", {}).get("positioning", "")
        preference_text = " ".join([str(positioning), *emphasis]).strip()
        if preference_text:
            chunks.append(
                {
                    "chunk_id": f"{record.mission_id}-positioning-preference",
                    "type": "user_positioning_preference",
                    "text": self.privacy.sanitize(
                        preference_text,
                        explicit_values=explicit,
                    ),
                    "mission_id": record.mission_id,
                    "persona_id": record.persona_id,
                    "persona_version": record.persona_version,
                    "assessor_verdict": record.assessor_verdict,
                    "privacy_transform_version": self.privacy.version,
                    "source_hashes": resolved.source_hashes,
                }
            )
        if not chunks:
            raise ResumePrivacyError(
                "no privacy-safe Ideation chunks remained after transformation"
            )
        return chunks

    @staticmethod
    def _embed_chunks(
        record: ResumeWorkflowRecord,
        chunks: list[dict[str, Any]],
        *,
        fixture: bool,
    ) -> dict[str, Any]:
        embeddings = []
        for item in chunks:
            digest = hashlib.sha256(item["text"].encode("utf-8")).digest()
            vector = [
                round((int.from_bytes(digest[index : index + 2], "big") / 32767.5) - 1, 6)
                for index in range(0, 16, 2)
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
            "vector_collection": (
                "resume_tailoring_phase2_synthetic"
                if fixture
                else "resume_tailoring_phase3_real_shadow"
            ),
            "production_vector_write": False,
            "embeddings": embeddings,
        }

    def _requirements(self, job: dict[str, Any]) -> list[dict[str, Any]]:
        return [
            {
                "id": item["id"],
                "text": item["text"].strip(),
                "required": bool(item.get("required", True)),
            }
            for item in job["requirements"]
            if item["text"].strip()
        ]

    def _evidence_catalog(
        self,
        profile: dict[str, Any],
    ) -> list[dict[str, Any]]:
        evidence: list[dict[str, Any]] = []
        for skill in profile.get("skills", []):
            if not isinstance(skill, str) or not skill.strip():
                continue
            text = skill.strip()
            evidence.append(
                {
                    "evidence_id": "skill-" + hashlib.sha256(
                        text.encode("utf-8")
                    ).hexdigest()[:12],
                    "type": "skill",
                    "text": text,
                    "employer": "",
                    "role_title": "",
                }
            )
        for experience_index, experience in enumerate(
            profile.get("experience", [])
        ):
            if not isinstance(experience, dict):
                continue
            for bullet_index, bullet in enumerate(experience.get("bullets", [])):
                if isinstance(bullet, str):
                    text = bullet.strip()
                    evidence_id = ""
                elif isinstance(bullet, dict):
                    text = str(bullet.get("text", "")).strip()
                    evidence_id = str(bullet.get("evidence_id", "")).strip()
                else:
                    continue
                if not text:
                    continue
                if not evidence_id:
                    evidence_id = (
                        f"exp-{experience_index + 1}-"
                        f"{bullet_index + 1}-"
                        f"{hashlib.sha256(text.encode('utf-8')).hexdigest()[:8]}"
                    )
                evidence.append(
                    {
                        "evidence_id": evidence_id,
                        "type": "experience_bullet",
                        "text": text,
                        "employer": str(experience.get("employer", "")),
                        "role_title": str(experience.get("role_title", "")),
                    }
                )
        return evidence

    def _map_evidence(
        self,
        requirements: list[dict[str, Any]],
        catalog: list[dict[str, Any]],
        *,
        emphasis: list[str],
    ) -> list[dict[str, Any]]:
        emphasis_tokens = self._tokens(" ".join(emphasis))
        mappings: list[dict[str, Any]] = []
        for requirement in requirements:
            requirement_tokens = self._tokens(requirement["text"])
            ranked = []
            for item in catalog:
                evidence_tokens = self._tokens(item["text"])
                overlap = len(requirement_tokens & evidence_tokens)
                emphasis_overlap = len(emphasis_tokens & evidence_tokens)
                score = overlap * 2 + emphasis_overlap
                if score:
                    ranked.append((score, item))
            ranked.sort(
                key=lambda pair: (
                    -pair[0],
                    pair[1]["evidence_id"],
                )
            )
            selected = [item for _, item in ranked[:3]]
            mappings.append(
                {
                    "requirement_id": requirement["id"],
                    "requirement_text": requirement["text"],
                    "required": requirement["required"],
                    "supporting_evidence_ids": [
                        item["evidence_id"] for item in selected
                    ],
                    "supporting_evidence": selected,
                }
            )
        return mappings

    def _build_real_draft(
        self,
        resolved: ResolvedResumeSources,
        catalog: list[dict[str, Any]],
        *,
        emphasis: list[str],
    ) -> str:
        profile = resolved.candidate.document
        job = resolved.job.document
        candidate = profile["candidate"]
        contact = candidate.get("contact", {})
        contact_values = []
        if isinstance(contact, dict):
            contact_values = [
                str(contact[field]).strip()
                for field in ("email", "phone", "location", "linkedin", "website")
                if contact.get(field)
            ]
        job_text = " ".join(
            [
                job.get("description", ""),
                *[
                    str(item.get("text", ""))
                    for item in job.get("requirements", [])
                    if isinstance(item, dict)
                ],
                *emphasis,
            ]
        )
        job_tokens = self._tokens(job_text)
        ranked_skills = sorted(
            [
                str(skill).strip()
                for skill in profile.get("skills", [])
                if str(skill).strip()
            ],
            key=lambda skill: (
                -len(self._tokens(skill) & job_tokens),
                skill.casefold(),
            ),
        )
        sections = [f"# {candidate['display_name'].strip()}"]
        if contact_values:
            sections.append(" | ".join(contact_values))
        sections.extend(
            [
                f"\n## Target Role\n\n{job['role_title'].strip()}",
                f"\n## Professional Summary\n\n{profile['summary'].strip()}",
            ]
        )
        if ranked_skills:
            sections.append(
                "\n## Core Skills\n\n" + " • ".join(ranked_skills[:16])
            )
        sections.append("\n## Professional Experience")
        evidence_by_context: dict[tuple[str, str], list[dict[str, Any]]] = {}
        for item in catalog:
            if item["type"] != "experience_bullet":
                continue
            key = (item["employer"], item["role_title"])
            evidence_by_context.setdefault(key, []).append(item)
        for experience in profile.get("experience", []):
            if not isinstance(experience, dict):
                continue
            employer = str(experience.get("employer", "")).strip()
            role = str(experience.get("role_title", "")).strip()
            dates = str(experience.get("dates", "")).strip()
            sections.append(
                f"\n### {role} — {employer}"
                + (f" ({dates})" if dates else "")
            )
            items = evidence_by_context.get((employer, role), [])
            ranked = sorted(
                items,
                key=lambda item: (
                    -len(self._tokens(item["text"]) & job_tokens),
                    item["evidence_id"],
                ),
            )
            selected = ranked[: min(5, len(ranked))]
            sections.extend(f"- {item['text']}" for item in selected)
        education = profile.get("education", [])
        if isinstance(education, list) and education:
            sections.append("\n## Education")
            for item in education:
                if isinstance(item, str):
                    sections.append(f"- {item}")
                elif isinstance(item, dict):
                    rendered = " — ".join(
                        str(item.get(field, "")).strip()
                        for field in ("credential", "institution")
                        if item.get(field)
                    )
                    if rendered:
                        sections.append(f"- {rendered}")
        return "\n".join(sections).rstrip() + "\n"

    @classmethod
    def _tokens(cls, text: str) -> set[str]:
        return {
            token
            for token in re.findall(r"[A-Za-z0-9+#.-]{2,}", text.casefold())
            if token not in cls.STOPWORDS
        }

    @staticmethod
    def _reject_inline_real_source_content(envelope: MissionEnvelope) -> None:
        nested = envelope.tool.parameters.get("resume_mission")
        if not isinstance(nested, dict):
            return
        references = list(nested.get("candidate_source_refs", []))
        target_job = nested.get("target_job", {})
        if isinstance(target_job, dict):
            references.append(target_job.get("description_ref"))
        allowed = {
            "source_id",
            "source_type",
            "uri",
            "content_hash",
            "authorization",
        }
        for reference in references:
            if isinstance(reference, dict) and set(reference) - allowed:
                raise ResumeWorkflowConflictError(
                    "real source references may contain metadata only; inline "
                    "content is not allowed"
                )

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
    ) -> dict[str, Any]:
        allowed = set(self.EVENT_TYPES) | set(self.OPTIONAL_EVENT_TYPES)
        if event_type not in allowed:
            raise ResumeWorkflowConflictError(
                f"unregistered résumé ledger event: {event_type}"
            )
        event = self.ledger.append(
            record.mission_id,
            event_type,
            record.state,
            details,
        )
        record.updated_at = utc_now()
        self._persist(record)
        return event

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
