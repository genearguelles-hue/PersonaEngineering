from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from ..models import (
    AdapterDescriptor,
    AdapterHealth,
    ExecutionRequest,
    ExecutionResult,
    GovernanceDecision,
    MissionEnvelope,
)


class ToolAdapter(ABC):
    """Transport-neutral lifecycle implemented by every Mission Control tool."""

    @abstractmethod
    def discover(self) -> AdapterDescriptor:
        """Return stable identity and capabilities."""

    @abstractmethod
    async def health(self) -> AdapterHealth:
        """Return runtime availability without mutating external state."""

    def capabilities(self) -> list[str]:
        return self.discover().capabilities

    async def configure(self, config: dict[str, Any]) -> dict[str, Any]:
        """Validate ephemeral configuration. Persistent changes are out of MC-1."""
        return {"accepted": True, "config": config}

    async def authorize(self, mission: MissionEnvelope) -> GovernanceDecision:
        """Perform the adapter-specific pre-execution policy decision."""
        allowed_actions = {"run", "smoke"}
        if mission.tool.action not in allowed_actions:
            return GovernanceDecision(
                decision="BLOCKED",
                rationale=f"Action '{mission.tool.action}' is not allowlisted.",
                policy_bindings=["PE-MC-TOOL-ACTION-ALLOWLIST"],
            )
        return GovernanceDecision(
            decision="AUTHORIZED",
            rationale="Mission satisfies the MC-1 adapter policy preflight.",
            policy_bindings=[
                "PE-MC-TOOL-ACTION-ALLOWLIST",
                "PE-MC-PERSONA-BINDING-REQUIRED",
                "PE-MC-EVIDENCE-REQUIRED",
            ],
            constraints={
                "persona_id": mission.persona_binding.persona_id,
                "adapter_id": mission.tool.adapter_id,
            },
        )

    @abstractmethod
    async def execute(self, request: ExecutionRequest) -> ExecutionResult:
        """Execute a previously authorized normalized request."""

    async def status(self, mission_id: str) -> dict[str, Any]:
        return {"mission_id": mission_id, "state": "managed_by_controller"}

    @abstractmethod
    async def cancel(self, mission_id: str) -> bool:
        """Request cancellation of an active tool process."""

    async def collect_evidence(self, mission_id: str) -> list[dict[str, Any]]:
        return []

    def normalize_result(self, result: ExecutionResult) -> ExecutionResult:
        return result

    def record_telemetry(self, result: ExecutionResult) -> dict[str, Any]:
        return result.telemetry.model_dump(mode="json")
