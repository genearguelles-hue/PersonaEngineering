from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ResumeWorkflowState(StrEnum):
    RECEIVED = "received"
    AUTHORIZED = "authorized"
    DRAFTING = "drafting"
    AWAITING_USER_REVISION = "awaiting_user_revision"
    AWAITING_USER_APPROVAL = "awaiting_user_approval"
    COMPLETED = "completed"
    FAILED = "failed"


class ResumeDecision(StrEnum):
    APPROVE = "approve"
    REVISE = "revise"


class ResumeDecisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: ResumeDecision
    reviewer_id: str = Field(min_length=2, max_length=128)
    notes: str = Field(default="", max_length=4000)
    corrections: list[str] = Field(default_factory=list, max_length=25)

    @model_validator(mode="after")
    def revision_requires_correction(self) -> "ResumeDecisionRequest":
        if self.decision == ResumeDecision.REVISE and not self.corrections:
            raise ValueError("revise requires at least one correction")
        if self.decision == ResumeDecision.APPROVE and self.corrections:
            raise ValueError("approve cannot include corrections")
        return self


class ResumePurgeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reviewer_id: str = Field(min_length=2, max_length=128)
    reason: str = Field(min_length=3, max_length=1000)
    confirmation: Literal["PURGE_SENSITIVE_ARTIFACTS"]


class ResumeAssessment(BaseModel):
    schema_version: str = "pe.resume-assessment.v1"
    assessor_id: str = "resume-persona-assessor@0.1.0"
    verdict: str
    requirement_coverage: float = Field(ge=0.0, le=1.0)
    unsupported_claim_count: int = Field(ge=0)
    privacy_findings: list[str] = Field(default_factory=list)
    findings: list[str] = Field(default_factory=list)
    assessed_at: datetime = Field(default_factory=utc_now)


class ResumeWorkflowRecord(BaseModel):
    schema_version: str = "pe.resume-workflow-record.v1"
    mission_id: str
    name: str
    persona_id: str
    persona_version: str
    state: ResumeWorkflowState
    authorization_decision: str | None = None
    assessor_verdict: str | None = None
    revision_count: int = Field(default=0, ge=0)
    final_artifact: str | None = None
    ideation_manifest: str | None = None
    error: str | None = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    metadata: dict[str, Any] = Field(default_factory=dict)
