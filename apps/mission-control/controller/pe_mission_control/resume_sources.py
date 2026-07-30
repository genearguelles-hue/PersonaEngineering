from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import unquote, urlparse

from .resume_privacy import PrivacyScan, ResumePrivacyTransformer


class ResumeSourceError(ValueError):
    pass


@dataclass(frozen=True)
class ResolvedSource:
    source_id: str
    source_type: str
    uri: str
    content_hash: str
    relative_path: str
    size_bytes: int
    document: dict[str, Any]
    privacy_scan: PrivacyScan

    def ledger_metadata(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "source_type": self.source_type,
            "uri_hash": hashlib.sha256(self.uri.encode("utf-8")).hexdigest(),
            "content_hash": self.content_hash,
            "size_bytes": self.size_bytes,
            "classification": self.privacy_scan.classification,
            "privacy_summary": self.privacy_scan.ledger_summary(),
        }


@dataclass(frozen=True)
class ResolvedResumeSources:
    candidate: ResolvedSource
    job: ResolvedSource

    @property
    def source_hashes(self) -> list[str]:
        return [self.candidate.content_hash, self.job.content_hash]


class ResumeSourceResolver:
    """Resolve hash-pinned JSON documents inside one local intake root."""

    candidate_schema = "pe.resume-candidate-profile.v1"
    job_schema = "pe.resume-job-description.v1"
    maximum_bytes = 1_048_576

    def __init__(self, settings: Any, privacy: ResumePrivacyTransformer):
        configured = getattr(settings, "resume_intake_root", None)
        raw_root = configured or os.environ.get("PE_RESUME_INTAKE_ROOT")
        self.root = (
            Path(raw_root).expanduser().resolve()
            if isinstance(raw_root, (str, os.PathLike)) and str(raw_root).strip()
            else None
        )
        self.privacy = privacy

    @property
    def configured(self) -> bool:
        return bool(self.root and self.root.is_dir())

    def resolve(self, nested: dict[str, Any]) -> ResolvedResumeSources:
        if not self.configured or self.root is None:
            raise ResumeSourceError(
                "PE_RESUME_INTAKE_ROOT must identify an existing local directory"
            )
        candidate_refs = nested.get("candidate_source_refs")
        if not isinstance(candidate_refs, list) or len(candidate_refs) != 1:
            raise ResumeSourceError(
                "Phase 3 requires exactly one canonical candidate source"
            )
        target_job = nested.get("target_job")
        if not isinstance(target_job, dict):
            raise ResumeSourceError("target_job must be an object")
        candidate = self._load(
            candidate_refs[0],
            expected_type="canonical_profile",
            expected_schema=self.candidate_schema,
        )
        job = self._load(
            target_job.get("description_ref"),
            expected_type="job_description",
            expected_schema=self.job_schema,
        )
        self._validate_candidate(candidate.document)
        self._validate_job(job.document)
        if candidate.document.get("schema_version") != self.candidate_schema:
            raise ResumeSourceError("candidate profile schema_version mismatch")
        if job.document.get("schema_version") != self.job_schema:
            raise ResumeSourceError("job description schema_version mismatch")
        return ResolvedResumeSources(candidate=candidate, job=job)

    def _load(
        self,
        reference: Any,
        *,
        expected_type: str,
        expected_schema: str,
    ) -> ResolvedSource:
        if not isinstance(reference, dict):
            raise ResumeSourceError(f"{expected_type} source reference is missing")
        if reference.get("source_type") != expected_type:
            raise ResumeSourceError(
                f"source_type must be {expected_type}"
            )
        if reference.get("authorization") != "user_authorized":
            raise ResumeSourceError("source authorization must be user_authorized")
        source_id = reference.get("source_id")
        uri = reference.get("uri")
        expected_hash = reference.get("content_hash")
        if not isinstance(source_id, str) or not source_id.strip():
            raise ResumeSourceError("source_id must be a non-empty string")
        if not isinstance(uri, str):
            raise ResumeSourceError("source uri must be a string")
        if (
            not isinstance(expected_hash, str)
            or len(expected_hash) != 64
            or any(character not in "0123456789abcdefABCDEF" for character in expected_hash)
        ):
            raise ResumeSourceError("source content_hash must be SHA-256 hex")
        relative = self._relative_from_uri(uri)
        assert self.root is not None
        unresolved = self.root / relative
        if unresolved.is_symlink():
            raise ResumeSourceError("symlink source files are not allowed")
        try:
            path = unresolved.resolve(strict=True)
            path.relative_to(self.root)
        except (FileNotFoundError, ValueError) as exc:
            raise ResumeSourceError(
                "source path is missing or escapes the intake root"
            ) from exc
        if path.suffix.casefold() != ".json" or not path.is_file():
            raise ResumeSourceError("source must be a regular JSON file")
        size = path.stat().st_size
        if size <= 0 or size > self.maximum_bytes:
            raise ResumeSourceError(
                f"source size must be between 1 and {self.maximum_bytes} bytes"
            )
        raw = path.read_bytes()
        actual_hash = hashlib.sha256(raw).hexdigest()
        if actual_hash.casefold() != expected_hash.casefold():
            raise ResumeSourceError(
                f"content hash mismatch for source_id={source_id}"
            )
        try:
            document = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ResumeSourceError("source must be valid UTF-8 JSON") from exc
        if not isinstance(document, dict):
            raise ResumeSourceError("source JSON must contain an object")
        if document.get("schema_version") != expected_schema:
            raise ResumeSourceError(
                f"source schema_version must be {expected_schema}"
            )
        privacy_scan = (
            self.privacy.scan_candidate_profile(document)
            if expected_type == "canonical_profile"
            else self.privacy.scan_job_description(document)
        )
        return ResolvedSource(
            source_id=source_id,
            source_type=expected_type,
            uri=uri,
            content_hash=actual_hash,
            relative_path=str(relative),
            size_bytes=size,
            document=document,
            privacy_scan=privacy_scan,
        )

    @staticmethod
    def _relative_from_uri(uri: str) -> Path:
        parsed = urlparse(uri)
        if parsed.scheme != "intake" or parsed.query or parsed.fragment:
            raise ResumeSourceError(
                "source uri must use intake:///relative/path.json"
            )
        if parsed.netloc:
            raise ResumeSourceError("intake uri must not contain a host")
        decoded = unquote(parsed.path).lstrip("/")
        pure = PurePosixPath(decoded)
        if (
            not decoded
            or pure.is_absolute()
            or any(part in {"", ".", ".."} for part in pure.parts)
        ):
            raise ResumeSourceError("invalid or traversing intake source path")
        return Path(*pure.parts)

    @staticmethod
    def _validate_candidate(document: dict[str, Any]) -> None:
        candidate = document.get("candidate")
        if not isinstance(candidate, dict):
            raise ResumeSourceError("candidate profile requires candidate object")
        if not isinstance(candidate.get("display_name"), str):
            raise ResumeSourceError("candidate.display_name is required")
        if not isinstance(document.get("summary"), str):
            raise ResumeSourceError("candidate profile summary is required")
        if not isinstance(document.get("skills"), list):
            raise ResumeSourceError("candidate profile skills must be an array")
        experience = document.get("experience")
        if not isinstance(experience, list) or not experience:
            raise ResumeSourceError(
                "candidate profile requires at least one experience record"
            )
        for item in experience:
            if not isinstance(item, dict) or not isinstance(item.get("bullets"), list):
                raise ResumeSourceError(
                    "each experience record requires a bullets array"
                )

    @staticmethod
    def _validate_job(document: dict[str, Any]) -> None:
        for field in ("employer", "role_title", "description"):
            if not isinstance(document.get(field), str):
                raise ResumeSourceError(f"job description requires {field}")
        requirements = document.get("requirements")
        if not isinstance(requirements, list) or not requirements:
            raise ResumeSourceError(
                "job description requires a non-empty requirements array"
            )
        for item in requirements:
            if (
                not isinstance(item, dict)
                or not isinstance(item.get("id"), str)
                or not isinstance(item.get("text"), str)
            ):
                raise ResumeSourceError(
                    "each job requirement requires string id and text"
                )
