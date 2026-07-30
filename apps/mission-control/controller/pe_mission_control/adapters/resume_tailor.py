from __future__ import annotations

from datetime import datetime, timezone
import os
from pathlib import Path
from typing import Any

from .base import ToolAdapter
from ..models import (
    AdapterDescriptor,
    AdapterHealth,
    ExecutionRequest,
    ExecutionResult,
    GovernanceDecision,
    MissionEnvelope,
    TokenTelemetry,
    ToolStatus,
)


class ResumeTailoringAdapter(ToolAdapter):
    """Governance boundary for synthetic and local real-data shadow workflows."""

    adapter_id = "resume-tailor"
    persona_id = "pe.resume_tailoring_specialist"

    def __init__(self, settings: Any):
        self.settings = settings

    def discover(self) -> AdapterDescriptor:
        return AdapterDescriptor(
            adapter_id=self.adapter_id,
            display_name="Governed Resume Tailoring",
            version="0.2.0",
            transport="in_process_cognitive_workflow",
            domain="career-evidence-transformation",
            capabilities=[
                "synthetic_fixture",
                "real_data_local_shadow",
                "hash_pinned_source_resolution",
                "evidence_mapping",
                "independent_assessment",
                "human_approval_pause",
                "privacy_sanitized_ideation_handoff",
            ],
            execution_mode="synthetic_and_real_shadow",
        )

    async def health(self) -> AdapterHealth:
        root_ready = self._intake_root_ready()
        return AdapterHealth(
            adapter_id=self.adapter_id,
            status="healthy",
            execution_mode="synthetic_and_real_shadow",
            details={
                "phase": 3,
                "real_candidate_data_allowed": root_ready,
                "real_data_mode": "local_shadow_only",
                "intake_root_configured": root_ready,
                "external_model_calls_allowed": False,
                "external_submission_allowed": False,
                "production_vector_write_allowed": False,
                "workflow_service_required": True,
            },
        )

    async def authorize(self, mission: MissionEnvelope) -> GovernanceDecision:
        failures: list[str] = []
        payload = mission.tool.parameters.get("resume_mission")
        if mission.governance_mode.value != "governed":
            failures.append("governance_mode must be governed")
        if mission.mission_type != "resume_tailoring":
            failures.append("mission_type must be resume_tailoring")
        if mission.persona_binding.persona_id != self.persona_id:
            failures.append(f"persona_binding must be {self.persona_id}")
        if mission.tool.adapter_id != self.adapter_id:
            failures.append(f"adapter_id must be {self.adapter_id}")
        if not isinstance(payload, dict):
            failures.append("tool.parameters.resume_mission must be an object")
        else:
            binding = payload.get("persona_binding", {})
            if binding.get("persona_id") != self.persona_id:
                failures.append("nested persona binding is invalid")
            governance = payload.get("governance", {})
            required_true = (
                "require_pre_execution_authorization",
                "require_persona_assessment",
                "require_ledger_terminal_event",
                "require_zero_unsupported_claims",
            )
            for field in required_true:
                if governance.get(field) is not True:
                    failures.append(f"governance.{field} must be true")
            output = payload.get("output", {})
            if output.get("application_ready_requires_user_approval") is not True:
                failures.append("explicit user approval must be required")
        fixture = mission.tool.parameters.get("fixture") is True
        if fixture:
            self._authorize_fixture(mission, payload, failures)
        else:
            self._authorize_real_shadow(mission, payload, failures)
        if failures:
            return GovernanceDecision(
                decision="BLOCKED",
                rationale="; ".join(failures),
                policy_bindings=[
                    "PE-RESUME-PHASE3-REAL-DATA-CONTROL",
                    "PE-RESUME-PERSONA-BINDING",
                    "PE-RESUME-HUMAN-APPROVAL",
                ],
            )
        return GovernanceDecision(
            decision="AUTHORIZED",
            rationale=(
                "Governed résumé mission satisfies the synthetic or local "
                "real-data shadow preflight."
            ),
            policy_bindings=[
                (
                    "PE-RESUME-PHASE2-SYNTHETIC-ONLY"
                    if fixture
                    else "PE-RESUME-PHASE3-LOCAL-SHADOW"
                ),
                "PE-RESUME-EVIDENCE-BOUNDARY",
                "PE-RESUME-INDEPENDENT-ASSESSOR",
                "PE-RESUME-HUMAN-APPROVAL",
                "PE-RESUME-IDEATION-PRIVACY-GATE",
            ],
            constraints={
                "persona_id": self.persona_id,
                "fixture_only": fixture,
                "real_candidate_data_allowed": not fixture,
                "local_processing_only": True,
                "external_submission_allowed": False,
                "production_vector_write_allowed": False,
            },
        )

    def _authorize_fixture(
        self,
        mission: MissionEnvelope,
        payload: Any,
        failures: list[str],
    ) -> None:
        if mission.tool.action != "smoke":
            failures.append("synthetic action must be smoke")
        if mission.constraints.get("synthetic_only") is not True:
            failures.append("synthetic mission requires constraints.synthetic_only=true")
        if isinstance(payload, dict) and (
            payload.get("schema_version") != "pe.resume_tailoring.mission.v1"
        ):
            failures.append("synthetic nested mission must use schema v1")

    def _authorize_real_shadow(
        self,
        mission: MissionEnvelope,
        payload: Any,
        failures: list[str],
    ) -> None:
        if mission.tool.action != "shadow":
            failures.append("real-data action must be shadow")
        if mission.constraints.get("real_data_mode") != "shadow":
            failures.append("constraints.real_data_mode must be shadow")
        if mission.constraints.get("no_external_submission") is not True:
            failures.append("constraints.no_external_submission must be true")
        if not self._intake_root_ready():
            failures.append(
                "PE_RESUME_INTAKE_ROOT must identify an existing local directory"
            )
        if not isinstance(payload, dict):
            return
        if payload.get("schema_version") != "pe.resume_tailoring.mission.v2":
            failures.append("real-data nested mission must use schema v2")
        controls = payload.get("real_data_controls")
        if not isinstance(controls, dict):
            failures.append("real_data_controls must be an object")
            return
        exact_values = {
            "processing_mode": "shadow",
            "purpose": "resume_tailoring",
            "user_consent": True,
            "local_processing_only": True,
            "external_model_calls": False,
            "external_submission": False,
            "production_vector_write": False,
            "sensitive_artifact_purge_requires_confirmation": True,
        }
        for field, expected in exact_values.items():
            if controls.get(field) != expected:
                failures.append(
                    f"real_data_controls.{field} must be {expected!r}"
                )
        consent_record_id = controls.get("consent_record_id")
        if not isinstance(consent_record_id, str) or len(consent_record_id) < 8:
            failures.append("real_data_controls.consent_record_id is required")
        retention_hours = controls.get("retention_hours")
        if (
            not isinstance(retention_hours, int)
            or isinstance(retention_hours, bool)
            or not 1 <= retention_hours <= 720
        ):
            failures.append("real_data_controls.retention_hours must be 1..720")
        privacy = payload.get("privacy", {})
        if privacy.get("ledger_payload_mode") != "hash_and_reference":
            failures.append("real-data Ledger mode must be hash_and_reference")
        if privacy.get("allow_employer_names_in_embeddings") is not False:
            failures.append("employer names must be excluded from embeddings")
        output = payload.get("output", {})
        if output.get("format") != "markdown":
            failures.append("Phase 3 shadow output format must be markdown")

    def _intake_root_ready(self) -> bool:
        configured = getattr(self.settings, "resume_intake_root", None)
        configured = configured or os.environ.get("PE_RESUME_INTAKE_ROOT")
        return bool(
            configured and Path(str(configured)).expanduser().is_dir()
        )

    async def execute(self, request: ExecutionRequest) -> ExecutionResult:
        """Fail closed if the generic terminal MC-1 path invokes this adapter."""
        now = datetime.now(timezone.utc)
        return ExecutionResult(
            request_id=request.request_id,
            mission_id=request.mission_id,
            adapter_id=self.adapter_id,
            status=ToolStatus.FAILED,
            started_at=now,
            completed_at=now,
            duration_ms=0,
            summary=(
                "Resume tailoring requires the pause/resume workflow endpoint; "
                "generic one-shot execution was rejected."
            ),
            telemetry=TokenTelemetry(provider_reported=False),
            raw_output={"required_endpoint": "/api/v1/resume-workflows"},
            error="resume workflow service required",
            fixture=True,
        )

    async def cancel(self, mission_id: str) -> bool:
        return True
