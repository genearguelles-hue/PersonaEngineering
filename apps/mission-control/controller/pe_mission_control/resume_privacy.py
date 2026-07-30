from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Iterable


class ResumePrivacyError(ValueError):
    pass


@dataclass(frozen=True)
class PrivacyScan:
    classification: str
    contact_pii_counts: dict[str, int] = field(default_factory=dict)
    blocked_findings: tuple[str, ...] = ()

    def ledger_summary(self) -> dict[str, Any]:
        return {
            "classification": self.classification,
            "contact_pii_counts": dict(self.contact_pii_counts),
            "blocked_finding_count": len(self.blocked_findings),
        }


class ResumePrivacyTransformer:
    """Fail-closed scan and deterministic redaction for résumé data."""

    version = "resume-real-shadow-redactor:0.2.0"

    EMAIL = re.compile(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}")
    PHONE = re.compile(
        r"(?<!\d)(?:\+?1[\s.-]?)?"
        r"(?:\(\d{3}\)|\d{3})[\s.-]?\d{3}[\s.-]?\d{4}(?!\d)"
    )
    URL = re.compile(r"\b(?:https?://|www\.)\S+", re.IGNORECASE)
    STREET = re.compile(
        r"\b\d{1,6}\s+[A-Za-z0-9.' -]{2,60}\s+"
        r"(?:street|st|avenue|ave|road|rd|boulevard|blvd|lane|ln|drive|dr|"
        r"court|ct|parkway|pkwy|place|pl)\b\.?",
        re.IGNORECASE,
    )
    SSN = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
    CARD = re.compile(r"\b(?:\d[ -]*?){13,19}\b")
    PRIVATE_KEY = re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")
    SECRET_ASSIGNMENT = re.compile(
        r"\b(?:api[_-]?key|access[_-]?token|refresh[_-]?token|password|"
        r"client[_-]?secret)\b\s*[:=]\s*\S+",
        re.IGNORECASE,
    )
    BEARER = re.compile(r"\bbearer\s+[A-Za-z0-9._~+/-]{8,}", re.IGNORECASE)

    FORBIDDEN_PROFILE_KEYS = {
        "ssn",
        "social_security_number",
        "passport_number",
        "drivers_license",
        "driver_license",
        "bank_account",
        "routing_number",
        "credit_card",
        "date_of_birth",
        "dob",
        "password",
        "api_key",
        "access_token",
        "refresh_token",
        "client_secret",
    }

    def scan_candidate_profile(self, value: dict[str, Any]) -> PrivacyScan:
        forbidden_keys = sorted(
            key
            for key in self._walk_keys(value)
            if key.casefold() in self.FORBIDDEN_PROFILE_KEYS
        )
        text = self._flatten_text(value)
        blocked = self._blocked_content_findings(text)
        blocked.extend(f"forbidden field: {key}" for key in forbidden_keys)
        scan = PrivacyScan(
            classification="real_candidate_personal_data",
            contact_pii_counts={
                "email": len(self.EMAIL.findall(text)),
                "phone": len(self.PHONE.findall(text)),
                "street_address": len(self.STREET.findall(text)),
                "url": len(self.URL.findall(text)),
            },
            blocked_findings=tuple(sorted(set(blocked))),
        )
        if scan.blocked_findings:
            raise ResumePrivacyError(
                "blocked high-risk identifier or secret in candidate source: "
                + "; ".join(scan.blocked_findings)
            )
        return scan

    def scan_job_description(self, value: dict[str, Any]) -> PrivacyScan:
        text = self._flatten_text(value)
        blocked = self._blocked_content_findings(text)
        scan = PrivacyScan(
            classification="real_job_description",
            contact_pii_counts={
                "email": len(self.EMAIL.findall(text)),
                "phone": len(self.PHONE.findall(text)),
                "street_address": len(self.STREET.findall(text)),
                "url": len(self.URL.findall(text)),
            },
            blocked_findings=tuple(sorted(set(blocked))),
        )
        if scan.blocked_findings:
            raise ResumePrivacyError(
                "blocked secret in job-description source: "
                + "; ".join(scan.blocked_findings)
            )
        return scan

    def scan_revision(self, values: Iterable[str]) -> None:
        text = "\n".join(values)
        blocked = self._blocked_content_findings(text)
        if blocked:
            raise ResumePrivacyError(
                "blocked high-risk identifier or secret in revision: "
                + "; ".join(sorted(set(blocked)))
            )

    def sanitize(
        self,
        text: str,
        *,
        explicit_values: Iterable[str] = (),
    ) -> str:
        sanitized = text
        replacements = sorted(
            {
                value.strip()
                for value in explicit_values
                if isinstance(value, str) and len(value.strip()) >= 2
            },
            key=len,
            reverse=True,
        )
        for value in replacements:
            sanitized = re.sub(
                re.escape(value),
                "[REDACTED]",
                sanitized,
                flags=re.IGNORECASE,
            )
        for pattern in (self.EMAIL, self.PHONE, self.URL, self.STREET):
            sanitized = pattern.sub("[REDACTED]", sanitized)
        sanitized = re.sub(r"(?:\[REDACTED\]\s*){2,}", "[REDACTED] ", sanitized)
        blocked = self._blocked_content_findings(sanitized)
        if blocked:
            raise ResumePrivacyError(
                "sanitized derivative still contains blocked data: "
                + "; ".join(sorted(set(blocked)))
            )
        if self.EMAIL.search(sanitized) or self.PHONE.search(sanitized):
            raise ResumePrivacyError(
                "sanitized derivative still contains contact PII"
            )
        return sanitized.strip()

    def draft_privacy_findings(
        self,
        text: str,
        *,
        allow_contact_pii: bool,
    ) -> list[str]:
        findings = self._blocked_content_findings(text)
        if not allow_contact_pii:
            if self.EMAIL.search(text):
                findings.append("prohibited contact PII: email")
            if self.PHONE.search(text):
                findings.append("prohibited contact PII: phone")
            if self.STREET.search(text):
                findings.append("prohibited contact PII: street address")
        return sorted(set(findings))

    def _blocked_content_findings(self, text: str) -> list[str]:
        patterns = (
            ("social security number", self.SSN),
            ("payment-card-like number", self.CARD),
            ("private key", self.PRIVATE_KEY),
            ("secret assignment", self.SECRET_ASSIGNMENT),
            ("bearer credential", self.BEARER),
        )
        return [label for label, pattern in patterns if pattern.search(text)]

    @classmethod
    def _flatten_text(cls, value: Any) -> str:
        parts: list[str] = []

        def visit(item: Any) -> None:
            if isinstance(item, dict):
                for key, nested in item.items():
                    parts.append(str(key))
                    visit(nested)
            elif isinstance(item, list):
                for nested in item:
                    visit(nested)
            elif item is not None:
                parts.append(str(item))

        visit(value)
        return "\n".join(parts)

    @classmethod
    def _walk_keys(cls, value: Any) -> Iterable[str]:
        if isinstance(value, dict):
            for key, nested in value.items():
                yield str(key)
                yield from cls._walk_keys(nested)
        elif isinstance(value, list):
            for nested in value:
                yield from cls._walk_keys(nested)
