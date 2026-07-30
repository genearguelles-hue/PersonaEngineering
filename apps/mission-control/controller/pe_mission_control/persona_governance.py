from __future__ import annotations

import hashlib
import json
import threading
from pathlib import Path
from typing import Any
from uuid import uuid4

from .models import (
    BehavioralIncidentCreate,
    BehavioralIncidentRecord,
    IncidentStatus,
    PersonaDeltaProposalCreate,
    PersonaDeltaProposalRecord,
    PersonaVersionRecord,
    ProposalReview,
    ProposalReviewRequest,
    ProposalStatus,
    RegressionComparisonCreate,
    RegressionComparisonRecord,
    ReviewDecision,
    utc_now,
)


class GovernanceRecordNotFoundError(KeyError):
    pass


class GovernanceConflictError(ValueError):
    pass


def _canonical_json(value: dict[str, Any]) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


class PersonaGovernanceStore:
    """Auditable proposal-only persistence for Persona Studio.

    Approval records governance consent to consider a new persona version. This
    store intentionally has no operation that mutates or activates a persona.
    """

    def __init__(self, data_dir: Path):
        self.root = data_dir / "persona_governance"
        self.incident_dir = self.root / "behavioral_incidents"
        self.proposal_dir = self.root / "persona_delta_proposals"
        self.comparison_dir = self.root / "regression_comparisons"
        self.history_dir = self.root / "history"
        for path in (
            self.incident_dir,
            self.proposal_dir,
            self.comparison_dir,
            self.history_dir,
        ):
            path.mkdir(parents=True, exist_ok=True)
        self.audit_path = self.root / "events.jsonl"
        self._lock = threading.RLock()

    def create_incident(
        self,
        payload: BehavioralIncidentCreate,
    ) -> BehavioralIncidentRecord:
        with self._lock:
            record = BehavioralIncidentRecord(
                **payload.model_dump(),
                incident_id=f"bi-{uuid4().hex[:12]}",
            )
            self._persist(
                self.incident_dir / f"{record.incident_id}.json",
                record.model_dump(mode="json"),
            )
            self._snapshot("incident", record.incident_id, record.model_dump(mode="json"))
            self._append_audit(
                "BEHAVIORAL_INCIDENT_RECORDED",
                "behavioral_incident",
                record.incident_id,
                {
                    "mission_id": record.mission_id,
                    "persona_id": record.persona_id,
                    "classification": record.classification,
                },
            )
            return record

    def list_incidents(self) -> list[BehavioralIncidentRecord]:
        records = [
            BehavioralIncidentRecord.model_validate(self._read(path))
            for path in self.incident_dir.glob("bi-*.json")
        ]
        return sorted(records, key=lambda item: item.created_at, reverse=True)

    def get_incident(self, incident_id: str) -> BehavioralIncidentRecord:
        path = self.incident_dir / f"{incident_id}.json"
        if not path.is_file():
            raise GovernanceRecordNotFoundError(incident_id)
        return BehavioralIncidentRecord.model_validate(self._read(path))

    def create_proposal(
        self,
        payload: PersonaDeltaProposalCreate,
    ) -> PersonaDeltaProposalRecord:
        with self._lock:
            incident = self.get_incident(payload.incident_id)
            if incident.persona_id != payload.persona_id:
                raise GovernanceConflictError(
                    "proposal persona_id must match the linked behavioral incident"
                )
            if incident.persona_version != payload.base_version:
                raise GovernanceConflictError(
                    "proposal base_version must match the incident persona_version"
                )
            record = PersonaDeltaProposalRecord(
                **payload.model_dump(),
                proposal_id=f"pdp-{uuid4().hex[:12]}",
            )
            self._persist(
                self.proposal_dir / f"{record.proposal_id}.json",
                record.model_dump(mode="json"),
            )
            self._snapshot("proposal", record.proposal_id, record.model_dump(mode="json"))
            self._append_audit(
                "PERSONA_DELTA_PROPOSED",
                "persona_delta_proposal",
                record.proposal_id,
                {
                    "incident_id": record.incident_id,
                    "persona_id": record.persona_id,
                    "base_version": record.base_version,
                    "proposed_version": record.proposed_version,
                    "application_status": "not_applied",
                },
            )
            return record

    def list_proposals(
        self,
        *,
        persona_id: str | None = None,
        incident_id: str | None = None,
        status: ProposalStatus | None = None,
    ) -> list[PersonaDeltaProposalRecord]:
        records = [
            PersonaDeltaProposalRecord.model_validate(self._read(path))
            for path in self.proposal_dir.glob("pdp-*.json")
        ]
        if persona_id:
            records = [item for item in records if item.persona_id == persona_id]
        if incident_id:
            records = [item for item in records if item.incident_id == incident_id]
        if status:
            records = [item for item in records if item.status == status]
        return sorted(records, key=lambda item: item.created_at, reverse=True)

    def get_proposal(self, proposal_id: str) -> PersonaDeltaProposalRecord:
        path = self.proposal_dir / f"{proposal_id}.json"
        if not path.is_file():
            raise GovernanceRecordNotFoundError(proposal_id)
        return PersonaDeltaProposalRecord.model_validate(self._read(path))

    def review_proposal(
        self,
        proposal_id: str,
        payload: ProposalReviewRequest,
    ) -> PersonaDeltaProposalRecord:
        with self._lock:
            record = self.get_proposal(proposal_id)
            if record.status != ProposalStatus.PENDING_REVIEW:
                raise GovernanceConflictError(
                    f"proposal is already {record.status}; review is immutable"
                )
            review = ProposalReview(**payload.model_dump())
            next_status = (
                ProposalStatus.APPROVED
                if payload.decision == ReviewDecision.APPROVE
                else ProposalStatus.REJECTED
            )
            record = record.model_copy(
                update={
                    "status": next_status,
                    "application_status": "not_applied",
                    "review_history": [*record.review_history, review],
                    "updated_at": utc_now(),
                }
            )
            self._persist(
                self.proposal_dir / f"{record.proposal_id}.json",
                record.model_dump(mode="json"),
            )
            self._snapshot("proposal", record.proposal_id, record.model_dump(mode="json"))
            self._append_audit(
                "PERSONA_DELTA_REVIEWED",
                "persona_delta_proposal",
                record.proposal_id,
                {
                    "decision": payload.decision,
                    "reviewer_id": payload.reviewer_id,
                    "application_status": "not_applied",
                },
            )
            return record

    def create_comparison(
        self,
        proposal_id: str,
        payload: RegressionComparisonCreate,
    ) -> RegressionComparisonRecord:
        with self._lock:
            proposal = self.get_proposal(proposal_id)
            record = RegressionComparisonRecord(
                **payload.model_dump(),
                comparison_id=f"prc-{uuid4().hex[:12]}",
                proposal_id=proposal.proposal_id,
                persona_id=proposal.persona_id,
                base_version=proposal.base_version,
                proposed_version=proposal.proposed_version,
            )
            self._persist(
                self.comparison_dir / f"{record.comparison_id}.json",
                record.model_dump(mode="json"),
            )
            self._snapshot(
                "comparison",
                record.comparison_id,
                record.model_dump(mode="json"),
            )
            self._append_audit(
                "PERSONA_REGRESSION_RECORDED",
                "regression_comparison",
                record.comparison_id,
                {
                    "proposal_id": proposal_id,
                    "verdict": record.verdict,
                    "metric_count": len(record.metrics),
                },
            )
            return record

    def list_comparisons(
        self,
        *,
        proposal_id: str | None = None,
    ) -> list[RegressionComparisonRecord]:
        records = [
            RegressionComparisonRecord.model_validate(self._read(path))
            for path in self.comparison_dir.glob("prc-*.json")
        ]
        if proposal_id:
            records = [item for item in records if item.proposal_id == proposal_id]
        return sorted(records, key=lambda item: item.created_at, reverse=True)

    def list_versions(self, persona_id: str) -> list[PersonaVersionRecord]:
        proposals = self.list_proposals(persona_id=persona_id)
        versions: dict[str, PersonaVersionRecord] = {}
        for proposal in proposals:
            versions.setdefault(
                proposal.base_version,
                PersonaVersionRecord(
                    persona_id=persona_id,
                    version=proposal.base_version,
                    lifecycle="active_baseline",
                    incident_id=proposal.incident_id,
                    applied=True,
                ),
            )
            versions[proposal.proposed_version] = PersonaVersionRecord(
                persona_id=persona_id,
                version=proposal.proposed_version,
                lifecycle=(
                    "approved_candidate"
                    if proposal.status == ProposalStatus.APPROVED
                    else "rejected_candidate"
                    if proposal.status == ProposalStatus.REJECTED
                    else "proposed_candidate"
                ),
                proposal_id=proposal.proposal_id,
                incident_id=proposal.incident_id,
                approved=proposal.status == ProposalStatus.APPROVED,
                applied=False,
                created_at=proposal.created_at,
            )
        return sorted(
            versions.values(),
            key=lambda item: tuple(int(part) for part in item.version.split(".")),
        )

    def audit_events(self) -> list[dict[str, Any]]:
        if not self.audit_path.exists():
            return []
        return [
            json.loads(line)
            for line in self.audit_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

    def verify_audit(self) -> dict[str, Any]:
        events = self.audit_events()
        previous_hash = "GENESIS"
        for index, event in enumerate(events):
            stored = event.get("event_hash")
            unsigned = {key: value for key, value in event.items() if key != "event_hash"}
            expected = hashlib.sha256(
                _canonical_json(unsigned).encode("utf-8")
            ).hexdigest()
            if event.get("previous_hash") != previous_hash or stored != expected:
                return {
                    "valid": False,
                    "event_count": len(events),
                    "failure_sequence": index + 1,
                }
            previous_hash = stored
        return {
            "valid": True,
            "event_count": len(events),
            "terminal_hash": previous_hash,
        }

    def _append_audit(
        self,
        event_type: str,
        subject_type: str,
        subject_id: str,
        details: dict[str, Any],
    ) -> None:
        events = self.audit_events()
        event = {
            "schema_version": "pe.persona-governance-event.v1",
            "sequence": len(events) + 1,
            "timestamp": utc_now().isoformat(),
            "event_type": event_type,
            "subject_type": subject_type,
            "subject_id": subject_id,
            "details": details,
            "previous_hash": events[-1]["event_hash"] if events else "GENESIS",
        }
        event["event_hash"] = hashlib.sha256(
            _canonical_json(event).encode("utf-8")
        ).hexdigest()
        with self.audit_path.open("a", encoding="utf-8") as handle:
            handle.write(_canonical_json(event) + "\n")

    def _snapshot(self, record_type: str, record_id: str, value: dict[str, Any]) -> None:
        directory = self.history_dir / record_type / record_id
        directory.mkdir(parents=True, exist_ok=True)
        revision = len(list(directory.glob("*.json"))) + 1
        self._persist(directory / f"{revision:04d}.json", value)

    @staticmethod
    def _read(path: Path) -> dict[str, Any]:
        return json.loads(path.read_text(encoding="utf-8"))

    @staticmethod
    def _persist(path: Path, value: dict[str, Any]) -> None:
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(
            json.dumps(value, indent=2, sort_keys=True, default=str) + "\n",
            encoding="utf-8",
        )
        temporary.replace(path)
