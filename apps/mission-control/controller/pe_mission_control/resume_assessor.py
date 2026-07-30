from __future__ import annotations

from typing import Any

from .resume_models import ResumeAssessment
from .resume_privacy import ResumePrivacyTransformer


class ResumePersonaAssessor:
    """Independent deterministic gate for synthetic and real shadow workflows."""

    assessor_id = "resume-persona-assessor@0.1.0"

    def __init__(self, privacy: ResumePrivacyTransformer | None = None):
        self.privacy = privacy or ResumePrivacyTransformer()

    def assess(
        self,
        *,
        evidence_map: list[dict[str, Any]],
        rejected_claims: list[dict[str, Any]],
        draft: str,
        minimum_coverage: float,
        allow_contact_pii: bool = False,
    ) -> ResumeAssessment:
        requirement_count = len(evidence_map)
        supported_count = sum(
            1 for item in evidence_map if item.get("supporting_evidence_ids")
        )
        coverage = (
            supported_count / requirement_count if requirement_count else 0.0
        )
        unsupported_claim_count = sum(
            1 for item in rejected_claims if not item.get("removed_from_draft")
        )
        privacy_findings = self.privacy.draft_privacy_findings(
            draft,
            allow_contact_pii=allow_contact_pii,
        )
        findings: list[str] = []
        if coverage < minimum_coverage:
            findings.append(
                f"requirement coverage {coverage:.3f} is below "
                f"{minimum_coverage:.3f}"
            )
        if unsupported_claim_count:
            findings.append("one or more unsupported claims remain in the draft")
        if privacy_findings:
            findings.append("draft contains prohibited synthetic-fixture PII")
        verdict = "pass" if not findings else "revise"
        return ResumeAssessment(
            assessor_id=self.assessor_id,
            verdict=verdict,
            requirement_coverage=coverage,
            unsupported_claim_count=unsupported_claim_count,
            privacy_findings=privacy_findings,
            findings=findings,
        )
