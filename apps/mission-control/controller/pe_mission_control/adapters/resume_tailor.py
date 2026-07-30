from __future__ import annotations

from datetime import datetime, timezone
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
    """Governance boundary for the resumè cognitive workflow.

    Phase 2 is deliberately fixture-only. The multi-stage workflow is executed
    by ResumeWorkflowService because the generic MC-1 adapter lifecycle is
    terminal and cannot represent human approval pauses.
    """

    adapter_id = "resume-tailor"
    persona_id = "pe.resume_tailoring_specialist"

    def __init__(self, settings: Any):
        self.settings = settings

    def discover(self) -> AdapterDescriptor:
        return AdapterDescriptor(
            adapter_id=self.adapter_id,
            display_name="Governed Resume Tailoring",
            version="0.1.0",
            transport="in_process_cognitive_workflow",
            domain="career-evidence-transformation",
            capabilities=[
                "synthetic_fixture",
                "evidence_mapping",
                "independent_assessment",
                "human_approval_pause",
                "privacy_sanitized_ideation_handoff",
            ],
            execution_mode="synthetic_only",
        )

    async def health(self) -> AdapterHealth:
        return AdapterHealth(
            adapter_id=self.adapter_id,
            status="healthy",
            execution_mode="synthetic_only",
            details={
                "phase": 2,
                "real_candidate_data_allowed": False,
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
        if mission.tool.action != "smoke":
            failures.append("Phase 2 action must be smoke")
        if mission.tool.parameters.get("fixture") is not True:
            failures.append("Phase 2 requires fixture=true")
        if mission.constraints.get("synthetic_only") is not True:
            failures.append("Phase 2 requires constraints.synthetic_only=true")
        if not isinstance(payload, dict):
            failures.append("tool.parameters.resume_mission must be an object")
        else:
            if payload.get("schema_version") != "pe.resume_tailoring.mission.v1":
                failures.append("invalid nested resume mission schema_version")
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
        if failures:
            return GovernanceDecision(
                decision="BLOCKED",
                rationale="; ".join(failures),
                policy_bindings=[
                    "PE-RESUME-PHASE2-SYNTHETIC-ONLY",
                    "PE-RESUME-PERSONA-BINDING",
                    "PE-RESUME-HUMAN-APPROVAL",
                ],
            )
        return GovernanceDecision(
            decision="AUTHORIZED",
            rationale=(
                "Synthetic governed résumé mission satisfies the Phase 2 "
                "cognitive-workflow preflight."
            ),
            policy_bindings=[
                "PE-RESUME-PHASE2-SYNTHETIC-ONLY",
                "PE-RESUME-EVIDENCE-BOUNDARY",
                "PE-RESUME-INDEPENDENT-ASSESSOR",
                "PE-RESUME-HUMAN-APPROVAL",
                "PE-RESUME-IDEATION-PRIVACY-GATE",
            ],
            constraints={
                "persona_id": self.persona_id,
                "fixture_only": True,
                "real_candidate_data_allowed": False,
            },
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
