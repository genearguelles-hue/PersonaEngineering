from __future__ import annotations

import asyncio
from typing import Any

from fastapi import FastAPI, HTTPException, Response, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from . import __version__
from .adapters import SeleniumPeCliAdapter
from .config import Settings
from .ledger import MissionLedger
from .mission_service import MissionNotFoundError, MissionService
from .models import (
    BehavioralIncidentCreate,
    MissionEnvelope,
    PersonaDeltaProposalCreate,
    ProposalReviewRequest,
    ProposalStatus,
    RegressionComparisonCreate,
    SystemHealth,
)
from .persona_governance import (
    GovernanceConflictError,
    GovernanceRecordNotFoundError,
    PersonaGovernanceStore,
)
from .registry import AdapterRegistry

settings = Settings.from_environment()
registry = AdapterRegistry()
registry.register(SeleniumPeCliAdapter(settings))
ledger = MissionLedger(settings.data_dir)
missions = MissionService(registry, ledger)
persona_governance = PersonaGovernanceStore(settings.data_dir)

app = FastAPI(
    title="Persona Engineering Control API",
    version=__version__,
    description="Local control plane for Persona Engineering Mission Control.",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:1420", "http://127.0.0.1:1420", "tauri://localhost"],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


@app.get("/api/v1/health", response_model=SystemHealth)
async def get_health() -> SystemHealth:
    adapter_health = await asyncio.gather(
        *(adapter.health() for adapter in registry.adapters())
    )
    status = (
        "healthy"
        if all(item.status == "healthy" for item in adapter_health)
        else "degraded"
    )
    return SystemHealth(
        status=status,
        version=__version__,
        execution_mode=settings.execution_mode,
        adapters=list(adapter_health),
    )


@app.get("/api/v1/adapters")
async def list_adapters():
    return registry.descriptors()


@app.get("/api/v1/adapters/{adapter_id}")
async def get_adapter(adapter_id: str):
    try:
        adapter = registry.get(adapter_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {
        "descriptor": adapter.discover(),
        "health": await adapter.health(),
    }


@app.post("/api/v1/missions/validate")
async def validate_mission(payload: dict[str, Any]):
    return missions.validate(payload)


@app.post("/api/v1/missions", status_code=202)
async def create_mission(envelope: MissionEnvelope):
    validation = missions.validate(envelope.model_dump(mode="json"))
    if not validation.valid:
        raise HTTPException(status_code=422, detail=validation.errors)
    return await missions.create(envelope.model_dump(mode="json", exclude_none=True))


@app.get("/api/v1/missions/{mission_id}")
async def get_mission(mission_id: str):
    try:
        return missions.get(mission_id)
    except MissionNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Mission not found") from exc


@app.get("/api/v1/missions/{mission_id}/events")
async def get_mission_events(mission_id: str):
    try:
        return missions.events(mission_id)
    except MissionNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Mission not found") from exc


@app.get("/api/v1/missions/{mission_id}/evidence")
async def get_mission_evidence(mission_id: str):
    try:
        return missions.evidence(mission_id)
    except MissionNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Mission not found") from exc


@app.post("/api/v1/missions/{mission_id}/cancel", status_code=202)
async def cancel_mission(mission_id: str):
    try:
        return await missions.cancel(mission_id)
    except MissionNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Mission not found") from exc


@app.post("/api/v1/behavioral-incidents", status_code=201)
async def create_behavioral_incident(payload: BehavioralIncidentCreate):
    if payload.mission_id:
        try:
            missions.get(payload.mission_id)
        except MissionNotFoundError as exc:
            raise HTTPException(
                status_code=404,
                detail="Linked mission not found",
            ) from exc
    return persona_governance.create_incident(payload)


@app.get("/api/v1/behavioral-incidents")
async def list_behavioral_incidents():
    return persona_governance.list_incidents()


@app.get("/api/v1/behavioral-incidents/{incident_id}")
async def get_behavioral_incident(incident_id: str):
    try:
        return persona_governance.get_incident(incident_id)
    except GovernanceRecordNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail="Behavioral incident not found",
        ) from exc


@app.post("/api/v1/persona-delta-proposals", status_code=201)
async def create_persona_delta_proposal(payload: PersonaDeltaProposalCreate):
    try:
        return persona_governance.create_proposal(payload)
    except GovernanceRecordNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail="Linked behavioral incident not found",
        ) from exc
    except GovernanceConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.get("/api/v1/persona-delta-proposals")
async def list_persona_delta_proposals(
    persona_id: str | None = None,
    incident_id: str | None = None,
    status: ProposalStatus | None = None,
):
    return persona_governance.list_proposals(
        persona_id=persona_id,
        incident_id=incident_id,
        status=status,
    )


@app.get("/api/v1/persona-delta-proposals/{proposal_id}")
async def get_persona_delta_proposal(proposal_id: str):
    try:
        return persona_governance.get_proposal(proposal_id)
    except GovernanceRecordNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail="Persona delta proposal not found",
        ) from exc


@app.post("/api/v1/persona-delta-proposals/{proposal_id}/review")
async def review_persona_delta_proposal(
    proposal_id: str,
    payload: ProposalReviewRequest,
):
    try:
        return persona_governance.review_proposal(proposal_id, payload)
    except GovernanceRecordNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail="Persona delta proposal not found",
        ) from exc
    except GovernanceConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.post(
    "/api/v1/persona-delta-proposals/{proposal_id}/regression-comparisons",
    status_code=201,
)
async def create_regression_comparison(
    proposal_id: str,
    payload: RegressionComparisonCreate,
):
    try:
        return persona_governance.create_comparison(proposal_id, payload)
    except GovernanceRecordNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail="Persona delta proposal not found",
        ) from exc


@app.get("/api/v1/persona-delta-proposals/{proposal_id}/regression-comparisons")
async def list_regression_comparisons(proposal_id: str):
    try:
        persona_governance.get_proposal(proposal_id)
    except GovernanceRecordNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail="Persona delta proposal not found",
        ) from exc
    return persona_governance.list_comparisons(proposal_id=proposal_id)


@app.get("/api/v1/personas/{persona_id}/versions")
async def list_persona_versions(persona_id: str):
    return persona_governance.list_versions(persona_id)


@app.get("/api/v1/persona-governance/integrity")
async def get_persona_governance_integrity():
    return persona_governance.verify_audit()


@app.websocket("/api/v1/ws/missions/{mission_id}")
async def stream_mission(websocket: WebSocket, mission_id: str):
    await websocket.accept()
    last_sequence = 0
    try:
        while True:
            try:
                record = missions.get(mission_id)
                events = missions.events(mission_id)
            except MissionNotFoundError:
                await websocket.send_json({"type": "error", "message": "Mission not found"})
                await websocket.close(code=4404)
                return
            new_events = [
                event for event in events if event["sequence"] > last_sequence
            ]
            if new_events:
                last_sequence = new_events[-1]["sequence"]
                await websocket.send_json(
                    {
                        "type": "mission_update",
                        "mission": record.model_dump(mode="json", exclude_none=True),
                        "events": new_events,
                    }
                )
            if record.state in {"completed", "failed", "cancelled"}:
                await websocket.close(code=1000)
                return
            await asyncio.sleep(0.25)
    except WebSocketDisconnect:
        return


@app.get("/", include_in_schema=False)
async def root() -> Response:
    return Response(
        content="Persona Engineering Mission Control API",
        media_type="text/plain",
    )
