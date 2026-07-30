from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from .resume_models import ResumeDecisionRequest
from .resume_workflow import (
    ResumeWorkflowConflictError,
    ResumeWorkflowNotFoundError,
    ResumeWorkflowService,
)


def build_resume_router(service: ResumeWorkflowService) -> APIRouter:
    router = APIRouter(prefix="/api/v1/resume-workflows", tags=["resume-workflows"])

    @router.post("", status_code=202)
    async def create_resume_workflow(payload: dict[str, Any]):
        try:
            return await service.create(payload)
        except ResumeWorkflowConflictError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @router.get("/{mission_id}")
    async def get_resume_workflow(mission_id: str):
        try:
            return service.get(mission_id)
        except ResumeWorkflowNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @router.post("/{mission_id}/decision")
    async def decide_resume_workflow(
        mission_id: str,
        request: ResumeDecisionRequest,
    ):
        try:
            return service.decide(mission_id, request)
        except ResumeWorkflowNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ResumeWorkflowConflictError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @router.get("/{mission_id}/events")
    async def get_resume_workflow_events(mission_id: str):
        try:
            return service.events(mission_id)
        except ResumeWorkflowNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @router.get("/{mission_id}/evidence")
    async def get_resume_workflow_evidence(mission_id: str):
        try:
            return service.evidence(mission_id)
        except ResumeWorkflowNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    return router
