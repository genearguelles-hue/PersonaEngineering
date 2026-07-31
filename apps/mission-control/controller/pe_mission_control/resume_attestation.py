from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class ResumePersonaBindingError(ValueError):
    """Raised when the requested persona cannot be resolved exactly."""


def _canonical_hash(value: Any) -> str:
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True)
class ResolvedResumePersona:
    persona_id: str
    persona_version: str
    persona_name: str
    persona_model: str
    persona_spec_path: str
    persona_spec_sha256: str
    runtime_contract_sha256: str
    engram_ids: tuple[str, ...]
    primitive_ids: tuple[str, ...]
    axiom_ids: tuple[str, ...]
    engrams_sha256: str
    primitives_sha256: str
    axioms_sha256: str
    registry_index_verified: bool

    def artifact(self) -> dict[str, Any]:
        return {
            "schema_version": "pe.resume-persona-binding.v1",
            "persona_id": self.persona_id,
            "persona_version": self.persona_version,
            "persona_name": self.persona_name,
            "persona_model": self.persona_model,
            "persona_spec_path": self.persona_spec_path,
            "persona_spec_sha256": self.persona_spec_sha256,
            "runtime_contract_sha256": self.runtime_contract_sha256,
            "active_components": {
                "engrams": {
                    "ids": list(self.engram_ids),
                    "sha256": self.engrams_sha256,
                },
                "primitives": {
                    "ids": list(self.primitive_ids),
                    "sha256": self.primitives_sha256,
                },
                "axioms": {
                    "ids": list(self.axiom_ids),
                    "sha256": self.axioms_sha256,
                },
            },
            "resolution": {
                "registry_type": "repository_persona_store",
                "exact_id_version_match": True,
                "registry_index_verified": self.registry_index_verified,
            },
        }

    def ledger_details(self, artifact_sha256: str) -> dict[str, Any]:
        return {
            "persona_id": self.persona_id,
            "persona_version": self.persona_version,
            "persona_model": self.persona_model,
            "persona_spec_sha256": self.persona_spec_sha256,
            "runtime_contract_sha256": self.runtime_contract_sha256,
            "engram_ids": list(self.engram_ids),
            "primitive_ids": list(self.primitive_ids),
            "axiom_ids": list(self.axiom_ids),
            "binding_artifact": "persona-binding.json",
            "binding_artifact_sha256": artifact_sha256,
            "exact_id_version_match": True,
            "registry_index_verified": self.registry_index_verified,
        }


class ResumePersonaRegistry:
    """Resolve an exact persona specification from the repository persona store."""

    EXPECTED_PERSONA_ID = "pe.resume_tailoring_specialist"
    EXPECTED_MISSION_TYPE = "resume_tailoring"
    EXPECTED_ADAPTER_ID = "resume-tailor"
    EXPECTED_PERSONA_MODEL = "Pi = <E, P, A>"

    def __init__(self, settings: Any, module_path: Path | None = None):
        self.settings = settings
        self.module_path = (module_path or Path(__file__)).resolve()
        self.repo_root = self._resolve_repo_root()
        self.persona_dir = self.repo_root / "personas"

    def resolve(
        self,
        persona_id: str,
        persona_version: str,
    ) -> ResolvedResumePersona:
        if persona_id != self.EXPECTED_PERSONA_ID:
            raise ResumePersonaBindingError(
                f"unsupported résumé persona id: {persona_id}"
            )
        candidates: list[tuple[Path, dict[str, Any], bytes]] = []
        for path in sorted(self.persona_dir.glob("*.persona.json")):
            document, raw = self._load_object(path)
            if (
                document.get("id") == persona_id
                and document.get("version") == persona_version
            ):
                candidates.append((path, document, raw))
        if not candidates:
            raise ResumePersonaBindingError(
                "no exact persona specification matches "
                f"{persona_id}@{persona_version}"
            )
        if len(candidates) != 1:
            paths = ", ".join(str(item[0].name) for item in candidates)
            raise ResumePersonaBindingError(
                "ambiguous persona specification match: " + paths
            )
        path, document, raw = candidates[0]
        self._validate_document(document)
        contract = document["runtime_contract"]
        engrams = document["engram_schema"]
        primitives = document["primitives"]
        axioms = document["axioms"]
        relative = path.relative_to(self.repo_root).as_posix()
        index_verified = self._verify_optional_index(
            persona_id,
            persona_version,
            path,
        )
        return ResolvedResumePersona(
            persona_id=persona_id,
            persona_version=persona_version,
            persona_name=document["name"],
            persona_model=contract["persona_model"],
            persona_spec_path=relative,
            persona_spec_sha256=hashlib.sha256(raw).hexdigest(),
            runtime_contract_sha256=_canonical_hash(contract),
            engram_ids=self._component_ids(engrams, "engram_schema"),
            primitive_ids=self._component_ids(primitives, "primitives"),
            axiom_ids=self._component_ids(axioms, "axioms"),
            engrams_sha256=_canonical_hash(engrams),
            primitives_sha256=_canonical_hash(primitives),
            axioms_sha256=_canonical_hash(axioms),
            registry_index_verified=index_verified,
        )

    def _resolve_repo_root(self) -> Path:
        configured = getattr(self.settings, "persona_registry_root", None)
        configured = configured or os.environ.get("PE_PERSONA_REGISTRY_ROOT")
        if configured:
            root = Path(str(configured)).expanduser().resolve()
            if not (root / "personas").is_dir():
                raise ResumePersonaBindingError(
                    "configured persona registry root has no personas directory"
                )
            return root
        for candidate in self.module_path.parents:
            if (candidate / "personas").is_dir():
                return candidate
        raise ResumePersonaBindingError(
            "unable to locate repository persona registry root"
        )

    @staticmethod
    def _load_object(path: Path) -> tuple[dict[str, Any], bytes]:
        try:
            raw = path.read_bytes()
            value = json.loads(raw.decode("utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ResumePersonaBindingError(
                f"invalid persona specification: {path.name}"
            ) from exc
        if not isinstance(value, dict):
            raise ResumePersonaBindingError(
                f"persona specification is not an object: {path.name}"
            )
        return value, raw

    def _validate_document(self, document: dict[str, Any]) -> None:
        required_arrays = ("engram_schema", "primitives", "axioms")
        for field in required_arrays:
            if not isinstance(document.get(field), list) or not document[field]:
                raise ResumePersonaBindingError(
                    f"persona specification requires non-empty {field}"
                )
        contract = document.get("runtime_contract")
        if not isinstance(contract, dict):
            raise ResumePersonaBindingError(
                "persona specification has no runtime_contract"
            )
        exact = {
            "persona_model": self.EXPECTED_PERSONA_MODEL,
            "mission_type": self.EXPECTED_MISSION_TYPE,
            "adapter_id": self.EXPECTED_ADAPTER_ID,
            "requires_pre_execution_authorization": True,
            "requires_independent_assessment": True,
            "requires_user_final_approval": True,
        }
        for field, expected in exact.items():
            if contract.get(field) != expected:
                raise ResumePersonaBindingError(
                    f"persona runtime_contract.{field} must be {expected!r}"
                )

    @staticmethod
    def _component_ids(
        components: list[Any],
        field: str,
    ) -> tuple[str, ...]:
        identifiers: list[str] = []
        for component in components:
            if not isinstance(component, dict):
                raise ResumePersonaBindingError(
                    f"{field} contains a non-object component"
                )
            identifier = component.get("id")
            if not isinstance(identifier, str) or not identifier:
                raise ResumePersonaBindingError(
                    f"{field} component has no non-empty id"
                )
            identifiers.append(identifier)
        if len(identifiers) != len(set(identifiers)):
            raise ResumePersonaBindingError(
                f"{field} contains duplicate component ids"
            )
        return tuple(identifiers)

    def _verify_optional_index(
        self,
        persona_id: str,
        persona_version: str,
        persona_path: Path,
    ) -> bool:
        index_path = self.persona_dir / "index.json"
        if not index_path.is_file():
            return False
        index, _raw = self._load_object(index_path)
        entries = index.get("personas")
        if not isinstance(entries, list):
            raise ResumePersonaBindingError(
                "persona registry index.personas must be an array"
            )
        matches = [
            entry
            for entry in entries
            if isinstance(entry, dict)
            and entry.get("id") == persona_id
            and entry.get("version") == persona_version
        ]
        if not matches:
            return False
        if len(matches) != 1:
            raise ResumePersonaBindingError(
                "persona registry index contains duplicate id/version entries"
            )
        filename = matches[0].get("file")
        if filename != persona_path.name:
            raise ResumePersonaBindingError(
                "persona registry index file does not match resolved specification"
            )
        return True
