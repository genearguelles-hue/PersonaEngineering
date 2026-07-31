from __future__ import annotations

from typing import Any

from .resume_models import ResumeAssessment
from .resume_privacy import ResumePrivacyTransformer


class ResumePersonaAssessor:
    """Independent deterministic gate for synthetic and real shadow workflows."""

    assessor_id = "resume-persona-assessor@0.2.0"
    LEVEL_WEIGHTS = {
        "strong": 1.0,
        "partial": 0.5,
        "adjacent": 0.0,
        "absent": 0.0,
    }

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
        requirement_results = []
        for item in evidence_map:
            classification = item.get("classification")
            if classification not in self.LEVEL_WEIGHTS:
                classification = (
                    "strong" if item.get("supporting_evidence_ids") else "absent"
                )
            requirement_results.append(
                {
                    "requirement_id": item.get("requirement_id"),
                    "required": item.get("required", True),
                    "classification": classification,
                    "coverage_weight": self.LEVEL_WEIGHTS[classification],
                    "rationale_code": item.get(
                        "rationale_code",
                        f"legacy:{classification}",
                    ),
                    "matched_capabilities": item.get(
                        "matched_capabilities",
                        [],
                    ),
                    "missing_capabilities": item.get(
                        "missing_capabilities",
                        [],
                    ),
                    "supporting_evidence_ids": item.get(
                        "supporting_evidence_ids",
                        [],
                    ),
                }
            )
        required_results = [
            item for item in requirement_results if item["required"]
        ]
        weighted_support = sum(
            item["coverage_weight"] for item in required_results
        )
        coverage = (
            weighted_support / len(required_results)
            if required_results
            else 0.0
        )
        counts = {
            level: sum(
                1
                for item in requirement_results
                if item["classification"] == level
            )
            for level in self.LEVEL_WEIGHTS
        }
        required_absent = [
            item["requirement_id"]
            for item in required_results
            if item["classification"] == "absent"
        ]
        required_adjacent = [
            item["requirement_id"]
            for item in required_results
            if item["classification"] == "adjacent"
        ]
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
        if required_absent:
            findings.append(
                "required capabilities are absent for: "
                + ", ".join(str(item) for item in required_absent)
            )
        if required_adjacent:
            findings.append(
                "adjacent evidence receives no coverage credit for: "
                + ", ".join(str(item) for item in required_adjacent)
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
            strong_count=counts["strong"],
            partial_count=counts["partial"],
            adjacent_count=counts["adjacent"],
            absent_count=counts["absent"],
            required_absent_count=len(required_absent),
            requirement_results=requirement_results,
            unsupported_claim_count=unsupported_claim_count,
            privacy_findings=privacy_findings,
            findings=findings,
        )
