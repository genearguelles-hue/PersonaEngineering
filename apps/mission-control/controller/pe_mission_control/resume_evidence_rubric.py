from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Iterable


@dataclass(frozen=True)
class RubricResult:
    classification: str
    weight: float
    rationale_code: str
    matched_capabilities: tuple[str, ...]
    missing_capabilities: tuple[str, ...]
    evidence: tuple[dict[str, Any], ...]


class ResumeEvidenceRubric:
    """Conservative deterministic requirement-to-evidence classifier."""

    version = "pe.resume-evidence-rubric.v1"
    LEVEL_WEIGHTS = {
        "strong": 1.0,
        "partial": 0.5,
        "adjacent": 0.0,
        "absent": 0.0,
    }
    STOPWORDS = {
        "a", "an", "and", "are", "as", "at", "be", "by", "for", "from",
        "in", "is", "of", "on", "or", "that", "the", "to", "with", "will",
    }
    CAPABILITY_ALIASES = {
        "workflow_analysis": (
            "workflow audit", "audit workflows", "audited workflows",
            "process improvement", "automation opportunities",
            "workflow assessment",
        ),
        "workflow_automation": (
            "workflow automation", "automation workflows", "automation for",
            "automated workflow", "test automation",
        ),
        "intake": ("intake",),
        "case_operations": ("case tracking", "case status", "case management"),
        "case_adjacent": (
            "complaint tracking", "tracking systems", "loan processing",
            "child welfare information system",
        ),
        "document_work": (
            "document review", "document summarization", "drafting assistance",
            "correspondence",
        ),
        "opportunity_identification": (
            "identify high value", "identify automation",
            "prioritize automation", "automation opportunities",
        ),
        "ai_tool_build": (
            "built ai", "developed ai", "ai prototype", "ai pilot",
            "generative ai", "ai assisted", "ai powered",
        ),
        "deployment": (
            "deployed", "production deployment", "shipped", "implemented",
        ),
        "summarization": ("summarization", "summarized"),
        "triage": ("triage",),
        "drafting": ("drafting", "draft generation"),
        "integration": (
            "integrate", "integrated", "integration", "connecting", "connected",
            "interfaces", "interoperability",
        ),
        "api": (" api ", "apis", "fastapi", "rest api"),
        "automation_platform": (
            "automation platform", "automation framework",
            "model context protocol", "mcp", "tool interface",
        ),
        "dashboard": ("dashboard", "control panel"),
        "infrastructure": (
            "infrastructure", "microservice", "containerized", "health check",
            "system status", "monitoring",
        ),
        "maintenance": ("maintain", "maintained", "ongoing operations"),
        "training": (
            "train staff", "trained", "training", "mentored", "consultation",
        ),
        "support": (
            "ongoing support", "user support", "supported production",
            "production readiness",
        ),
        "feedback_iteration": (
            "feedback", "iteration", "iterated", "continuous improvement",
        ),
        "vendor_evaluation": (
            "vendor", "procurement", "platform evaluation", "vetted",
            "vendor assessment",
        ),
        "privacy_confidentiality": (
            "privacy", "confidentiality", "data protection", "sensitive data",
        ),
        "legal_domain": (
            "legal practice", "law firm", "legal operations", "client data",
        ),
        "regulated_domain": (
            "regulated", "compliance", "fda", "iso 13485", "medical device",
            "banking",
        ),
        "measurement": (
            "measure", "measured", "tracked", "benchmarked", "report",
            "telemetry",
        ),
        "time_saved": ("time saved", "hours saved", "labor saved"),
        "efficiency": (
            "efficiency", "performance", "token consumption", "cost savings",
            "latency",
        ),
        "deployed_outcomes": (
            "deployed tools", "production tools", "operational outcomes",
            "in production",
        ),
    }

    def classify(
        self,
        requirement: dict[str, Any],
        catalog: list[dict[str, Any]],
        *,
        emphasis: list[str] | None = None,
    ) -> RubricResult:
        requirement_text = self._normalize(requirement["text"])
        family = self._family(requirement_text)
        relevant = self._relevant_capabilities(family)
        ranked = self._rank_evidence(
            requirement_text,
            catalog,
            relevant,
            emphasis or [],
        )
        selected = tuple(item for _, item in ranked[:3])
        aggregate: set[str] = set()
        for item in selected:
            aggregate.update(self._capabilities(item["text"]))

        evaluator = getattr(self, f"_evaluate_{family}")
        classification, required = evaluator(requirement_text, aggregate, selected)
        matched = tuple(sorted(aggregate & relevant))
        missing = tuple(sorted(required - aggregate))
        if classification == "absent":
            selected = ()
        return RubricResult(
            classification=classification,
            weight=self.LEVEL_WEIGHTS[classification],
            rationale_code=f"{family}:{classification}",
            matched_capabilities=matched,
            missing_capabilities=missing,
            evidence=selected,
        )

    def _rank_evidence(
        self,
        requirement_text: str,
        catalog: list[dict[str, Any]],
        relevant: set[str],
        emphasis: list[str],
    ) -> list[tuple[int, dict[str, Any]]]:
        requirement_tokens = self._tokens(requirement_text)
        emphasis_tokens = self._tokens(" ".join(emphasis))
        ranked: list[tuple[int, dict[str, Any]]] = []
        for item in catalog:
            evidence_text = self._normalize(str(item.get("text", "")))
            capabilities = self._capabilities(evidence_text)
            capability_overlap = len(capabilities & relevant)
            lexical_overlap = len(requirement_tokens & self._tokens(evidence_text))
            emphasis_overlap = len(emphasis_tokens & self._tokens(evidence_text))
            score = capability_overlap * 20 + lexical_overlap * 2 + emphasis_overlap
            if score >= 4:
                decorated = dict(item)
                decorated["rubric_capabilities"] = sorted(capabilities & relevant)
                ranked.append((score, decorated))
        ranked.sort(key=lambda pair: (-pair[0], pair[1]["evidence_id"]))
        return ranked

    def _family(self, text: str) -> str:
        if "vendor" in text or "vet ai" in text:
            return "vendor_privacy"
        if "case management" in text and self._contains_any(
            text, ("integrate", "integration")
        ):
            return "case_integration"
        if self._contains_any(text, ("time saved", "efficiency gained")):
            return "efficiency"
        if self._contains_any(text, ("train staff", "ongoing support", "feedback")):
            return "training_support"
        if self._contains_any(text, ("api", "dashboard", "infrastructure")):
            return "infrastructure"
        if self._contains_any(
            text, ("summarization", "intake triage", "drafting assistance")
        ):
            return "internal_ai_tools"
        if self._contains_any(
            text,
            ("audit", "automation opportunities", "document review", "correspondence"),
        ):
            return "workflow_audit"
        return "fallback"

    def _relevant_capabilities(self, family: str) -> set[str]:
        groups = {
            "workflow_audit": {
                "workflow_analysis", "workflow_automation", "intake",
                "case_operations", "case_adjacent", "document_work",
                "opportunity_identification",
            },
            "internal_ai_tools": {
                "ai_tool_build", "deployment", "summarization", "triage",
                "drafting", "case_operations", "integration",
            },
            "case_integration": {
                "integration", "case_operations", "case_adjacent", "deployment",
            },
            "infrastructure": {
                "api", "automation_platform", "dashboard", "infrastructure",
                "maintenance", "deployment",
            },
            "training_support": {"training", "support", "feedback_iteration"},
            "vendor_privacy": {
                "vendor_evaluation", "privacy_confidentiality", "legal_domain",
                "regulated_domain", "ai_tool_build",
            },
            "efficiency": {
                "measurement", "time_saved", "efficiency",
                "deployed_outcomes", "deployment",
            },
        }
        return groups.get(family, set(self.CAPABILITY_ALIASES))

    @staticmethod
    def _evaluate_workflow_audit(
        _text: str,
        capabilities: set[str],
        _evidence: tuple[dict[str, Any], ...],
    ) -> tuple[str, set[str]]:
        required = {
            "workflow_analysis", "case_operations", "document_work",
            "opportunity_identification",
        }
        breadth = len(capabilities & required)
        if "workflow_analysis" in capabilities and breadth >= 3:
            return "strong", required
        if "workflow_analysis" in capabilities or (
            "workflow_automation" in capabilities
            and capabilities & {"case_operations", "case_adjacent"}
        ):
            return "partial", required
        if capabilities & {"workflow_automation", "case_adjacent", "document_work"}:
            return "adjacent", required
        return "absent", required

    @staticmethod
    def _evaluate_internal_ai_tools(
        _text: str,
        capabilities: set[str],
        _evidence: tuple[dict[str, Any], ...],
    ) -> tuple[str, set[str]]:
        required = {
            "ai_tool_build", "deployment", "summarization", "triage",
            "drafting", "case_operations",
        }
        use_cases = capabilities & {
            "summarization", "triage", "drafting", "case_operations",
        }
        if {"ai_tool_build", "deployment"} <= capabilities and len(use_cases) >= 2:
            return "strong", required
        if "ai_tool_build" in capabilities:
            return "partial", required
        if capabilities & {"integration", "deployment"}:
            return "adjacent", required
        return "absent", required

    @staticmethod
    def _evaluate_case_integration(
        _text: str,
        capabilities: set[str],
        _evidence: tuple[dict[str, Any], ...],
    ) -> tuple[str, set[str]]:
        required = {"integration", "case_operations", "deployment"}
        if required <= capabilities:
            return "strong", required
        if {"integration", "case_operations"} <= capabilities:
            return "partial", required
        if capabilities & {"integration", "case_operations", "case_adjacent"}:
            return "adjacent", required
        return "absent", required

    @staticmethod
    def _evaluate_infrastructure(
        text: str,
        capabilities: set[str],
        _evidence: tuple[dict[str, Any], ...],
    ) -> tuple[str, set[str]]:
        required = {
            capability
            for capability, trigger in (
                ("api", "api"),
                ("automation_platform", "automation platform"),
                ("dashboard", "dashboard"),
                ("infrastructure", "infrastructure"),
                ("maintenance", "maintain"),
            )
            if trigger in text
        } or {"api", "automation_platform", "infrastructure"}
        coverage = len(required & capabilities) / len(required)
        if coverage == 1.0:
            return "strong", required
        if coverage >= 0.4:
            return "partial", required
        if capabilities & {
            "api", "automation_platform", "infrastructure", "deployment",
        }:
            return "adjacent", required
        return "absent", required

    @staticmethod
    def _evaluate_training_support(
        _text: str,
        capabilities: set[str],
        _evidence: tuple[dict[str, Any], ...],
    ) -> tuple[str, set[str]]:
        required = {"training", "support", "feedback_iteration"}
        if required <= capabilities:
            return "strong", required
        if "training" in capabilities or {
            "support", "feedback_iteration",
        } <= capabilities:
            return "partial", required
        if capabilities & required:
            return "adjacent", required
        return "absent", required

    @staticmethod
    def _evaluate_vendor_privacy(
        _text: str,
        capabilities: set[str],
        _evidence: tuple[dict[str, Any], ...],
    ) -> tuple[str, set[str]]:
        required = {
            "vendor_evaluation", "privacy_confidentiality", "legal_domain",
        }
        if required <= capabilities:
            return "strong", required
        if "vendor_evaluation" in capabilities and capabilities & {
            "privacy_confidentiality", "regulated_domain",
        }:
            return "partial", required
        if capabilities & {
            "vendor_evaluation", "privacy_confidentiality", "legal_domain",
            "regulated_domain", "ai_tool_build",
        }:
            return "adjacent", required
        return "absent", required

    @staticmethod
    def _evaluate_efficiency(
        _text: str,
        capabilities: set[str],
        _evidence: tuple[dict[str, Any], ...],
    ) -> tuple[str, set[str]]:
        required = {"measurement", "time_saved", "deployed_outcomes"}
        if required <= capabilities:
            return "strong", required
        if "measurement" in capabilities and capabilities & {
            "time_saved", "efficiency", "deployment",
        }:
            return "partial", required
        if capabilities & {"measurement", "efficiency", "time_saved"}:
            return "adjacent", required
        return "absent", required

    def _evaluate_fallback(
        self,
        text: str,
        _capabilities: set[str],
        evidence: tuple[dict[str, Any], ...],
    ) -> tuple[str, set[str]]:
        requirement_tokens = self._tokens(text)
        evidence_tokens = self._tokens(
            " ".join(str(item.get("text", "")) for item in evidence)
        )
        required = {f"token:{token}" for token in requirement_tokens}
        if not requirement_tokens:
            return "absent", required
        overlap = requirement_tokens & evidence_tokens
        recall = len(overlap) / len(requirement_tokens)
        if recall >= 0.65 and len(overlap) >= 3:
            return "strong", required
        if recall >= 0.4 and len(overlap) >= 2:
            return "partial", required
        if recall >= 0.2:
            return "adjacent", required
        return "absent", required

    def _capabilities(self, text: str) -> set[str]:
        normalized = f" {self._normalize(text)} "
        observed = set()
        for capability, aliases in self.CAPABILITY_ALIASES.items():
            if any(f" {self._normalize(alias)} " in normalized for alias in aliases):
                observed.add(capability)
        return observed

    def _tokens(self, text: str) -> set[str]:
        return {
            token
            for token in re.findall(r"[a-z0-9]+", self._normalize(text))
            if len(token) >= 3 and token not in self.STOPWORDS
        }

    @staticmethod
    def _normalize(text: str) -> str:
        return re.sub(
            r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", text.casefold())
        ).strip()

    @staticmethod
    def _contains_any(text: str, values: Iterable[str]) -> bool:
        return any(value in text for value in values)
