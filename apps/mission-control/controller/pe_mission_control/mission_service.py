from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any
from uuid import uuid4

from pydantic import ValidationError

from .canonical import build_canonical_mission
from .ledger import MissionLedger
from .models import (
    ExecutionRequest,
    GovernanceMode,
    MissionEnvelope,
    MissionRecord,
    MissionState,
    ToolStatus,
    ValidationResult,
    utc_now,
)
from .registry import AdapterRegistry


class MissionNotFoundError(KeyError):
    pass


class MissionService:
    def __init__(self, registry: AdapterRegistry, ledger: MissionLedger):
        self.registry = registry
        self.ledger = ledger
        self._records: dict[str, MissionRecord] = {}
        self._tasks: dict[str, asyncio.Task[None]] = {}

    def validate(self, payload: dict[str, Any]) -> ValidationResult:
        try:
            envelope = MissionEnvelope.model_validate(payload)
            self.registry.get(envelope.tool.adapter_id)
        except (ValidationError, KeyError, ValueError) as exc:
            if isinstance(exc, ValidationError):
                errors = [
                    f"{'.'.join(str(part) for part in item['loc'])}: {item['msg']}"
                    for item in exc.errors()
                ]
            else:
                errors = [str(exc)]
            return ValidationResult(valid=False, errors=errors)
        return ValidationResult(
            valid=True,
            normalized=envelope.model_dump(mode="json", exclude_none=True),
        )

    async def create(self, payload: dict[str, Any]) -> MissionRecord:
        envelope = MissionEnvelope.model_validate(payload)
        adapter = self.registry.get(envelope.tool.adapter_id)
        mission_id = envelope.mission_id or f"pe-mc-{uuid4().hex[:12]}"
        envelope = envelope.model_copy(update={"mission_id": mission_id})
        now = utc_now()
        record = MissionRecord(
            mission_id=mission_id,
            name=envelope.name,
            state=MissionState.ACCEPTED,
            governance_mode=envelope.governance_mode,
            adapter_id=envelope.tool.adapter_id,
            created_at=now,
            updated_at=now,
        )
        self._records[mission_id] = record
        mission_dir = self.ledger.mission_dir(mission_id)
        operator_request = envelope.model_dump(mode="json", exclude_none=True)
        self._write_json(mission_dir / "operator-request.json", operator_request)
        runtime_envelope = operator_request
        if envelope.governance_mode == GovernanceMode.GOVERNED:
            runtime_envelope = build_canonical_mission(envelope, mission_id, now)
            self._write_json(mission_dir / "mission.json", runtime_envelope)
        self.ledger.append(
            mission_id,
            "MISSION_ACCEPTED",
            record.state,
            {
                "adapter_id": envelope.tool.adapter_id,
                "governance_mode": envelope.governance_mode,
            },
        )

        decision = await adapter.authorize(envelope)
        record.authorization = decision
        if decision.decision == "BLOCKED":
            record.state = MissionState.FAILED
            record.error = decision.rationale
            record.updated_at = utc_now()
            self.ledger.append(
                mission_id,
                "AUTHORIZATION_BLOCKED",
                record.state,
                decision.model_dump(mode="json"),
            )
            self._persist_record(record)
            self.ledger.seal_manifest(mission_id)
            return record

        record.state = MissionState.AUTHORIZED
        record.updated_at = utc_now()
        self.ledger.append(
            mission_id,
            "AUTHORIZATION_DECIDED",
            record.state,
            decision.model_dump(mode="json"),
        )
        self._persist_record(record)
        self._tasks[mission_id] = asyncio.create_task(
            self._run(envelope, runtime_envelope, record),
            name=f"pe-mission-{mission_id}",
        )
        return record

    async def _run(
        self,
        envelope: MissionEnvelope,
        runtime_envelope: dict[str, Any],
        record: MissionRecord,
    ) -> None:
        adapter = self.registry.get(envelope.tool.adapter_id)
        mission_dir = self.ledger.mission_dir(record.mission_id)
        record.state = MissionState.RUNNING
        record.updated_at = utc_now()
        self._persist_record(record)
        self.ledger.append(
            record.mission_id,
            "TOOL_EXECUTION_STARTED",
            record.state,
            {"adapter_id": envelope.tool.adapter_id, "action": envelope.tool.action},
        )
        parameters = dict(envelope.tool.parameters)
        timeout = int(parameters.get("timeout_seconds", 120))
        request = ExecutionRequest(
            request_id=f"req-{uuid4().hex[:12]}",
            mission_id=record.mission_id,
            action=envelope.tool.action,
            parameters=parameters,
            timeout_seconds=timeout,
            artifact_directory=str(mission_dir),
            governance_context=(
                record.authorization.model_dump(mode="json")
                if record.authorization
                else {}
            ),
            mission_envelope=runtime_envelope,
        )
        try:
            result = await adapter.execute(request)
            record.result = adapter.normalize_result(result)
            record.state = (
                MissionState.COMPLETED
                if result.status == ToolStatus.PASSED
                else MissionState.CANCELLED
                if result.status == ToolStatus.CANCELLED
                else MissionState.FAILED
            )
            record.error = result.error
            self._write_json(
                mission_dir / "normalized-result.json",
                result.model_dump(mode="json", exclude_none=True),
            )
            self.ledger.append(
                record.mission_id,
                "TOOL_EXECUTION_COMPLETED",
                record.state,
                {
                    "status": result.status,
                    "duration_ms": result.duration_ms,
                    "exit_code": result.exit_code,
                    "fixture": result.fixture,
                },
            )
            self.ledger.append(
                record.mission_id,
                "RUNTIME_VERDICT_RECORDED",
                record.state,
                {
                    "verdict": "PASS"
                    if result.status == ToolStatus.PASSED
                    else "FAIL",
                    "basis": "normalized tool result",
                    "assessor": "not_invoked_in_mc1",
                },
            )
        except asyncio.CancelledError:
            await adapter.cancel(record.mission_id)
            record.state = MissionState.CANCELLED
            record.error = "Mission task cancelled."
            self.ledger.append(
                record.mission_id,
                "MISSION_CANCELLED",
                record.state,
            )
        except Exception as exc:  # boundary: convert adapter failure to evidence
            record.state = MissionState.FAILED
            record.error = str(exc)
            self.ledger.append(
                record.mission_id,
                "MISSION_FAILED",
                record.state,
                {"error": str(exc)},
            )
        finally:
            record.updated_at = utc_now()
            self._persist_record(record)
            self.ledger.append(
                record.mission_id,
                "MISSION_TERMINATED",
                record.state,
                {"terminal_state": record.state},
            )
            self.ledger.seal_manifest(record.mission_id)
            self._tasks.pop(record.mission_id, None)

    def get(self, mission_id: str) -> MissionRecord:
        record = self._records.get(mission_id)
        if record is None:
            path = self.ledger.missions_dir / mission_id / "mission-record.json"
            if path.exists():
                record = MissionRecord.model_validate_json(
                    path.read_text(encoding="utf-8")
                )
                self._records[mission_id] = record
        if record is None:
            raise MissionNotFoundError(mission_id)
        return record

    def events(self, mission_id: str) -> list[dict[str, Any]]:
        self.get(mission_id)
        return self.ledger.events(mission_id)

    def evidence(self, mission_id: str) -> dict[str, Any]:
        self.get(mission_id)
        return self.ledger.manifest(mission_id) or {
            "mission_id": mission_id,
            "sealed": False,
            "ledger": self.ledger.verify(mission_id),
            "artifacts": [],
        }

    async def cancel(self, mission_id: str) -> MissionRecord:
        record = self.get(mission_id)
        task = self._tasks.get(mission_id)
        adapter = self.registry.get(record.adapter_id)
        await adapter.cancel(mission_id)
        if task and not task.done():
            task.cancel()
        return record

    def _persist_record(self, record: MissionRecord) -> None:
        path = self.ledger.mission_dir(record.mission_id) / "mission-record.json"
        self._write_json(path, record.model_dump(mode="json", exclude_none=True))

    @staticmethod
    def _write_json(path: Path, value: dict[str, Any]) -> None:
        path.write_text(
            json.dumps(value, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
