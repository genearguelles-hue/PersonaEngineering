from __future__ import annotations

from datetime import datetime
from typing import Any

from .models import GovernanceMode, MissionEnvelope


def build_canonical_mission(
    envelope: MissionEnvelope,
    mission_id: str,
    requested_at: datetime,
) -> dict[str, Any]:
    """Translate a Mission Control launch request into canonical pe.mission.v1.

    The desktop API intentionally presents an operator-oriented form. The
    governance runtime accepts the stricter canonical mission envelope. This
    function is the explicit anti-corruption layer between those contracts.
    """

    if envelope.governance_mode != GovernanceMode.GOVERNED:
        raise ValueError(
            "The authoritative pe.mission.v1 runtime currently permits only "
            "governed missions. Ungoverned live execution is not supported."
        )
    if envelope.tool.adapter_id != "selenium":
        raise ValueError("MC-1.1 canonical translation supports Selenium only.")

    parameters = envelope.tool.parameters
    base_url = str(
        parameters.get("target_url")
        or parameters.get("base_url")
        or "https://www.saucedemo.com"
    ).rstrip("/")
    scenario = str(parameters.get("scenario", "saucedemo_checkout"))
    suite_id = (
        "checkout-smoke"
        if scenario in {"saucedemo_checkout", "checkout-smoke"}
        else scenario.replace("_", "-")
    )
    timeout_seconds = int(parameters.get("timeout_seconds", 120))

    return {
        "schema_version": "pe.mission.v1",
        "mission_id": mission_id,
        "mission_type": "ui_test",
        "requested_at": requested_at.isoformat().replace("+00:00", "Z"),
        "requested_by": {
            "actor_id": "gene",
            "source": "dashboard",
        },
        "purpose": envelope.name,
        "persona_bindings": {
            "planner": {
                "persona_id": "test-designer",
                "version": "1.0.0",
            },
            "executor": {
                "persona_id": envelope.persona_binding.persona_id,
                "version": envelope.persona_binding.version or "1.0.0",
            },
            "assessor": {
                "persona_id": "test-results-assessor",
                "version": "1.0.0",
            },
        },
        "tool_request": {
            "tool": "selenium",
            "capability": "selenium.execute_suite",
            "operation": "run",
            "parameters": {
                "suite_id": suite_id,
                "browser": str(parameters.get("browser", "chrome")),
                "headless": bool(parameters.get("headless", True)),
                "base_url": base_url,
                "test_data_profile": "saucedemo-standard",
                "tags": ["smoke", "checkout"],
            },
        },
        "governance": {
            "mode": "governed",
            "risk_class": "low",
            "approval_policy": "automatic_within_boundary",
            "policy_set": "pe-test-execution.v1",
        },
        "constraints": {
            "environment": "local",
            "timeout_seconds": timeout_seconds,
            "max_retries": 0,
            "network_scope": "allowlisted_targets_only",
        },
        "evidence_requirements": {
            "ledger_required": True,
            "report_required": True,
            "screenshots": "failure_only",
            "artifact_manifest": True,
            "logs": True,
            "retention_days": 30,
        },
        "acceptance_criteria": {
            "require_zero_failures": True,
            "minimum_passed_tests": 2,
            "maximum_duration_seconds": timeout_seconds,
        },
        "labels": {
            "application": "saucedemo",
            "release_gate": "smoke",
        },
    }
