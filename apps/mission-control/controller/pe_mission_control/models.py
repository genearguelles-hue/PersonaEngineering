from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class GovernanceMode(StrEnum):
    GOVERNED = "governed"
    UNGOVERNED = "ungoverned"


class MissionState(StrEnum):
    ACCEPTED = "accepted"
    AUTHORIZED = "authorized"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ToolStatus(StrEnum):
    PASSED = "passed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    ERROR = "error"


class IncidentStatus(StrEnum):
    OPEN = "open"
    UNDER_REVIEW = "under_review"
    RESOLVED = "resolved"
    DISMISSED = "dismissed"


class IncidentClassification(StrEnum):
    BEHAVIORAL_DEVIATION = "behavioral_deviation"
    POLICY_VIOLATION = "policy_violation"
    INCONSISTENT_OUTPUT = "inconsistent_output"
    BOUNDARY_BREACH = "boundary_breach"
    OTHER = "other"


class ProposalStatus(StrEnum):
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    REJECTED = "rejected"


class ReviewDecision(StrEnum):
    APPROVE = "approve"
    REJECT = "reject"


class RegressionVerdict(StrEnum):
    PASS = "pass"
    FAIL = "fail"
    INCOMPLETE = "incomplete"


class PersonaBinding(BaseModel):
    model_config = ConfigDict(extra="allow")

    persona_id: str = Field(min_length=1)
    version: str | None = None


class ToolBinding(BaseModel):
    model_config = ConfigDict(extra="allow")

    adapter_id: str = Field(min_length=1)
    action: str = Field(default="run", min_length=1)
    parameters: dict[str, Any] = Field(default_factory=dict)


class MissionEnvelope(BaseModel):
    """Stable MC-1 projection of the extensible pe.mission.v1 envelope."""

    model_config = ConfigDict(extra="allow")

    schema_version: str
    mission_id: str | None = None
    name: str = Field(min_length=3, max_length=200)
    mission_type: str
    governance_mode: GovernanceMode
    persona_binding: PersonaBinding
    tool: ToolBinding
    objectives: list[str] = Field(default_factory=list)
    constraints: dict[str, Any] = Field(default_factory=dict)
    telemetry: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_contract(self) -> "MissionEnvelope":
        if self.schema_version != "pe.mission-control.launch.v1":
            raise ValueError(
                "schema_version must be pe.mission-control.launch.v1"
            )
        if self.mission_type == "web_test" and self.tool.adapter_id != "selenium":
            raise ValueError("MC-1 web_test missions require the selenium adapter")
        return self


class AdapterDescriptor(BaseModel):
    adapter_id: str
    display_name: str
    version: str
    transport: str
    domain: str
    capabilities: list[str]
    execution_mode: str


class AdapterHealth(BaseModel):
    adapter_id: str
    status: str
    execution_mode: str
    details: dict[str, Any] = Field(default_factory=dict)


class GovernanceDecision(BaseModel):
    decision: str
    rationale: str
    policy_bindings: list[str] = Field(default_factory=list)
    constraints: dict[str, Any] = Field(default_factory=dict)


class ExecutionRequest(BaseModel):
    request_id: str
    mission_id: str
    action: str
    parameters: dict[str, Any]
    timeout_seconds: int = Field(default=120, ge=1, le=3600)
    artifact_directory: str
    governance_context: dict[str, Any] = Field(default_factory=dict)
    mission_envelope: dict[str, Any]


class EvidenceItem(BaseModel):
    kind: str
    path: str
    sha256: str | None = None


class TokenTelemetry(BaseModel):
    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)
    reasoning_tokens: int | None = Field(default=None, ge=0)
    total_tokens: int | None = Field(default=None, ge=0)
    estimated_cost_usd: float | None = Field(default=None, ge=0)
    provider_reported: bool = False


class ExecutionResult(BaseModel):
    schema_version: str = "pe.tool-result.v1"
    request_id: str
    mission_id: str
    adapter_id: str
    status: ToolStatus
    started_at: datetime
    completed_at: datetime
    duration_ms: int = Field(ge=0)
    summary: str
    exit_code: int | None = None
    evidence: list[EvidenceItem] = Field(default_factory=list)
    telemetry: TokenTelemetry = Field(default_factory=TokenTelemetry)
    raw_output: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None
    fixture: bool = False


class MissionRecord(BaseModel):
    mission_id: str
    name: str
    state: MissionState
    governance_mode: GovernanceMode
    adapter_id: str
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    authorization: GovernanceDecision | None = None
    result: ExecutionResult | None = None
    error: str | None = None


class ValidationResult(BaseModel):
    valid: bool
    errors: list[str] = Field(default_factory=list)
    normalized: dict[str, Any] | None = None


class SystemHealth(BaseModel):
    status: str
    service: str = "pe-mission-control"
    version: str
    execution_mode: str
    adapters: list[AdapterHealth]


class BehavioralIncidentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mission_id: str | None = None
    persona_id: str = Field(min_length=1)
    persona_version: str = Field(min_length=1)
    classification: IncidentClassification
    title: str = Field(min_length=3, max_length=160)
    description: str = Field(min_length=10, max_length=4000)
    evidence_refs: list[str] = Field(default_factory=list, max_length=50)
    reported_by: str = Field(min_length=2, max_length=128)


class BehavioralIncidentRecord(BehavioralIncidentCreate):
    schema_version: str = "pe.behavioral-incident.v1"
    incident_id: str
    status: IncidentStatus = IncidentStatus.OPEN
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class PrimitiveChange(BaseModel):
    model_config = ConfigDict(extra="forbid")

    primitive_id: str = Field(min_length=1, max_length=128)
    operation: str = Field(pattern="^(add|replace|remove)$")
    current_value: Any | None = None
    proposed_value: Any | None = None
    rationale: str = Field(min_length=5, max_length=2000)


class PersonaDeltaProposalCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    incident_id: str
    persona_id: str = Field(min_length=1)
    base_version: str = Field(pattern=r"^[0-9]+\.[0-9]+\.[0-9]+$")
    proposed_version: str = Field(pattern=r"^[0-9]+\.[0-9]+\.[0-9]+$")
    title: str = Field(min_length=3, max_length=160)
    hypothesis: str = Field(min_length=10, max_length=4000)
    primitive_changes: list[PrimitiveChange] = Field(min_length=1, max_length=50)
    safety_constraints: list[str] = Field(default_factory=list, max_length=50)
    regression_objectives: list[str] = Field(default_factory=list, max_length=50)
    proposed_by: str = Field(min_length=2, max_length=128)

    @model_validator(mode="after")
    def versions_must_differ(self) -> "PersonaDeltaProposalCreate":
        base = tuple(int(part) for part in self.base_version.split("."))
        proposed = tuple(int(part) for part in self.proposed_version.split("."))
        if proposed <= base:
            raise ValueError("proposed_version must be greater than base_version")
        return self


class ProposalReview(BaseModel):
    decision: ReviewDecision
    reviewer_id: str = Field(min_length=2, max_length=128)
    notes: str = Field(min_length=3, max_length=4000)
    reviewed_at: datetime = Field(default_factory=utc_now)


class PersonaDeltaProposalRecord(PersonaDeltaProposalCreate):
    schema_version: str = "pe.persona-delta-proposal.v1"
    proposal_id: str
    status: ProposalStatus = ProposalStatus.PENDING_REVIEW
    application_status: str = "not_applied"
    review_history: list[ProposalReview] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class ProposalReviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: ReviewDecision
    reviewer_id: str = Field(min_length=2, max_length=128)
    notes: str = Field(min_length=3, max_length=4000)


class RegressionMetric(BaseModel):
    model_config = ConfigDict(extra="forbid")

    metric: str = Field(min_length=1, max_length=128)
    baseline: float
    candidate: float
    unit: str = Field(default="score", min_length=1, max_length=32)
    objective: str = Field(pattern="^(increase|decrease|maintain)$")
    passed: bool


class RegressionComparisonCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    baseline_mission_id: str | None = None
    candidate_mission_id: str | None = None
    metrics: list[RegressionMetric] = Field(min_length=1, max_length=100)
    verdict: RegressionVerdict
    notes: str = Field(default="", max_length=4000)
    recorded_by: str = Field(min_length=2, max_length=128)


class RegressionComparisonRecord(RegressionComparisonCreate):
    schema_version: str = "pe.persona-regression-comparison.v1"
    comparison_id: str
    proposal_id: str
    persona_id: str
    base_version: str
    proposed_version: str
    created_at: datetime = Field(default_factory=utc_now)


class PersonaVersionRecord(BaseModel):
    persona_id: str
    version: str
    lifecycle: str
    proposal_id: str | None = None
    incident_id: str | None = None
    approved: bool = False
    applied: bool = False
    created_at: datetime | None = None
