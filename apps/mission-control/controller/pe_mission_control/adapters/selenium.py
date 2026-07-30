from __future__ import annotations

import asyncio
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from time import monotonic
from typing import Any

from ..config import Settings
from ..models import (
    AdapterDescriptor,
    AdapterHealth,
    EvidenceItem,
    ExecutionRequest,
    ExecutionResult,
    GovernanceDecision,
    GovernanceMode,
    MissionEnvelope,
    TokenTelemetry,
    ToolStatus,
)
from ..result_contracts import (
    ResultContractError,
    load_runtime_tool_result,
    verify_selenium_result_contract,
)
from .base import ToolAdapter


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


class SeleniumPeCliAdapter(ToolAdapter):
    """Normalized adapter for the existing pe.mission.v1 Selenium CLI path."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self._processes: dict[str, asyncio.subprocess.Process] = {}

    def discover(self) -> AdapterDescriptor:
        return AdapterDescriptor(
            adapter_id="selenium",
            display_name="Selenium PE CLI",
            version="0.2.1",
            transport="cli",
            domain="web_testing",
            capabilities=[
                "discover",
                "health",
                "capabilities",
                "configure",
                "authorize",
                "execute",
                "status",
                "cancel",
                "collect_evidence",
                "normalize_result",
                "record_telemetry",
                "headless_browser",
                "screenshot_evidence",
                "pe.mission.v1",
            ],
            execution_mode=self.settings.execution_mode,
        )

    async def health(self) -> AdapterHealth:
        root = self.settings.persona_engineering_root
        root_exists = bool(root and root.is_dir())
        if self.settings.execution_mode == "fixture":
            return AdapterHealth(
                adapter_id="selenium",
                status="healthy",
                execution_mode="fixture",
                details={
                    "message": "Deterministic fixture adapter is ready.",
                    "persona_engineering_root_configured": root is not None,
                },
            )
        module_available = False
        module_path: str | None = None
        probe_error: str | None = None
        if root_exists:
            try:
                probe = await asyncio.create_subprocess_exec(
                    self.settings.python_executable,
                    "-c",
                    "import pe_mission; print(pe_mission.__file__)",
                    cwd=str(root),
                    env=os.environ.copy(),
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout, stderr = await asyncio.wait_for(
                    probe.communicate(),
                    timeout=5,
                )
                module_available = probe.returncode == 0
                module_path = (
                    stdout.decode("utf-8", errors="replace").strip() or None
                )
                probe_error = (
                    stderr.decode("utf-8", errors="replace").strip() or None
                )
            except (OSError, RuntimeError, TimeoutError) as exc:
                probe_error = str(exc)

        return AdapterHealth(
            adapter_id="selenium",
            status="healthy" if root_exists and module_available else "degraded",
            execution_mode="real",
            details={
                "persona_engineering_root": str(root) if root else None,
                "root_exists": root_exists,
                "python_executable": self.settings.python_executable,
                "module_available": module_available,
                "module_path": module_path,
                "probe_error": probe_error,
            },
        )

    async def authorize(self, mission: MissionEnvelope) -> GovernanceDecision:
        if mission.governance_mode == GovernanceMode.UNGOVERNED:
            if self.settings.execution_mode == "real":
                return GovernanceDecision(
                    decision="BLOCKED",
                    rationale=(
                        "The authoritative pe.mission.v1 runtime permits only "
                        "governed missions. Live ungoverned execution is not "
                        "supported by the current canonical schema."
                    ),
                    policy_bindings=["PE-MISSION-V1-GOVERNED-ONLY"],
                )
            return GovernanceDecision(
                decision="BYPASSED",
                rationale="Ungoverned fixture comparison mode explicitly selected.",
                policy_bindings=["PE-MC-MATCHED-COMPARISON-MODE"],
            )
        return await super().authorize(mission)

    async def execute(self, request: ExecutionRequest) -> ExecutionResult:
        if self.settings.execution_mode == "fixture":
            return await self._execute_fixture(request)
        return await self._execute_real(request)

    async def _execute_fixture(self, request: ExecutionRequest) -> ExecutionResult:
        started = _utc_now()
        clock = monotonic()
        await asyncio.sleep(0.35)
        artifact_dir = Path(request.artifact_directory)
        artifact_dir.mkdir(parents=True, exist_ok=True)
        evidence_path = artifact_dir / "selenium-fixture-evidence.json"
        evidence_payload = {
            "schema_version": "pe.selenium.fixture-evidence.v1",
            "mission_id": request.mission_id,
            "fixture": True,
            "scenario": request.parameters.get("scenario", "saucedemo_checkout"),
            "observations": [
                {"name": "login", "status": "passed"},
                {"name": "checkout_complete", "status": "passed"},
            ],
            "notice": "Deterministic evidence; no live browser was launched.",
        }
        evidence_path.write_text(
            json.dumps(evidence_payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        completed = _utc_now()
        return ExecutionResult(
            request_id=request.request_id,
            mission_id=request.mission_id,
            adapter_id="selenium",
            status=ToolStatus.PASSED,
            started_at=started,
            completed_at=completed,
            duration_ms=max(1, int((monotonic() - clock) * 1000)),
            summary="Fixture Selenium checkout mission completed successfully.",
            exit_code=0,
            evidence=[
                EvidenceItem(
                    kind="fixture_observations",
                    path=str(evidence_path),
                    sha256=_sha256(evidence_path),
                )
            ],
            telemetry=TokenTelemetry(
                input_tokens=820,
                output_tokens=204,
                reasoning_tokens=0,
                total_tokens=1024,
                estimated_cost_usd=0.0,
                provider_reported=False,
            ),
            raw_output={
                "scenario": request.parameters.get("scenario"),
                "observations_passed": 2,
                "observations_total": 2,
            },
            fixture=True,
        )

    async def _execute_real(self, request: ExecutionRequest) -> ExecutionResult:
        started = _utc_now()
        clock = monotonic()
        root = self.settings.persona_engineering_root
        if root is None or not root.is_dir():
            return self._error_result(
                request,
                started,
                clock,
                "PERSONA_ENGINEERING_ROOT is missing or is not a directory.",
            )

        artifact_dir = Path(request.artifact_directory)
        artifact_dir.mkdir(parents=True, exist_ok=True)
        mission_path = artifact_dir / "mission.json"
        if not mission_path.exists():
            mission_path.write_text(
                json.dumps(request.mission_envelope, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )

        env = os.environ.copy()
        env["PE_MISSION_CONTROL_MISSION_ID"] = request.mission_id
        env["PE_MISSION_CONTROL_ARTIFACT_DIR"] = str(artifact_dir)
        validation_command = [
            self.settings.python_executable,
            "-m",
            "pe_mission",
            "validate",
            str(mission_path),
        ]
        try:
            validation_process = await asyncio.create_subprocess_exec(
                *validation_command,
                cwd=str(root),
                env=env,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            validation_stdout, validation_stderr = await asyncio.wait_for(
                validation_process.communicate(),
                timeout=15,
            )
        except (OSError, RuntimeError, TimeoutError) as exc:
            return self._error_result(
                request,
                started,
                clock,
                f"Canonical mission validation could not run: {exc}",
            )

        validation_path = artifact_dir / "runtime-validation.json"
        validation_path.write_bytes(validation_stdout)
        validation_error_path = artifact_dir / "runtime-validation.stderr.log"
        validation_error_path.write_bytes(validation_stderr)
        validation_payload = self._parse_json_output(
            validation_stdout.decode("utf-8", errors="replace")
        )
        if (
            validation_process.returncode != 0
            or validation_payload.get("decision") != "valid"
        ):
            errors = validation_payload.get("errors") or [
                validation_stderr.decode("utf-8", errors="replace").strip()
            ]
            return self._error_result(
                request,
                started,
                clock,
                "Canonical pe.mission.v1 validation failed: "
                + "; ".join(str(item) for item in errors if item),
                exit_code=validation_process.returncode,
            )

        command = [
            self.settings.python_executable,
            "-m",
            "pe_mission",
            "run",
            str(mission_path),
            "--adapter",
            "pe-cli",
            "--persona-engineering-root",
            str(root),
        ]
        try:
            process = await asyncio.create_subprocess_exec(
                *command,
                cwd=str(root),
                env=env,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            self._processes[request.mission_id] = process
            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=request.timeout_seconds,
                )
            except TimeoutError:
                process.terminate()
                await process.wait()
                return self._error_result(
                    request,
                    started,
                    clock,
                    f"Selenium mission exceeded {request.timeout_seconds} seconds.",
                    exit_code=process.returncode,
                )
            finally:
                self._processes.pop(request.mission_id, None)
        except (OSError, RuntimeError) as exc:
            return self._error_result(request, started, clock, str(exc))

        stdout_path = artifact_dir / "selenium-stdout.log"
        stderr_path = artifact_dir / "selenium-stderr.log"
        stdout_path.write_bytes(stdout)
        stderr_path.write_bytes(stderr)
        parsed = self._parse_json_output(stdout.decode("utf-8", errors="replace"))
        evidence = [
            EvidenceItem(
                kind="stdout",
                path=str(stdout_path),
                sha256=_sha256(stdout_path),
            ),
            EvidenceItem(
                kind="stderr",
                path=str(stderr_path),
                sha256=_sha256(stderr_path),
            ),
        ]
        result_contract: dict[str, Any]
        try:
            source_result_path, source_result = load_runtime_tool_result(
                parsed.get("run_dir")
            )
            criteria = request.mission_envelope.get("acceptance_criteria", {})
            result_contract = verify_selenium_result_contract(
                source_result,
                minimum_passed_tests=int(
                    criteria.get("minimum_passed_tests", 1)
                ),
                maximum_duration_seconds=float(
                    criteria.get(
                        "maximum_duration_seconds",
                        request.timeout_seconds,
                    )
                ),
                require_zero_failures=bool(
                    criteria.get("require_zero_failures", True)
                ),
            )
            result_contract["source_result_path"] = str(source_result_path)
            copied_result_path = artifact_dir / "authoritative-tool-result.json"
            copied_result_path.write_text(
                json.dumps(source_result, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            evidence.append(
                EvidenceItem(
                    kind="authoritative_tool_result",
                    path=str(copied_result_path),
                    sha256=_sha256(copied_result_path),
                )
            )
        except ResultContractError as exc:
            result_contract = {
                "schema_version": "pe.selenium-result-contract-verification.v1",
                "valid": False,
                "error": str(exc),
            }
        contract_path = artifact_dir / "selenium-result-contract.json"
        contract_path.write_text(
            json.dumps(result_contract, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        evidence.append(
            EvidenceItem(
                kind="result_contract_verification",
                path=str(contract_path),
                sha256=_sha256(contract_path),
            )
        )
        parsed["result_contract"] = result_contract
        status = ToolStatus.PASSED if process.returncode == 0 else ToolStatus.FAILED
        contract_disagreement = bool(
            process.returncode != 0 and result_contract.get("valid") is True
        )
        completed = _utc_now()
        telemetry = self._extract_telemetry(parsed)

        return ExecutionResult(
            request_id=request.request_id,
            mission_id=request.mission_id,
            adapter_id="selenium",
            status=status,
            started_at=started,
            completed_at=completed,
            duration_ms=max(1, int((monotonic() - clock) * 1000)),
            summary=(
                "Selenium PE CLI mission completed."
                if status == ToolStatus.PASSED
                else (
                    "Selenium evidence passed the normalized result contract, "
                    "but the authoritative runtime returned a finding. Apply "
                    "the bundled pe_mission assessor compatibility patch and rerun."
                )
                if contract_disagreement
                else "Selenium PE CLI mission failed."
            ),
            exit_code=process.returncode,
            evidence=evidence,
            telemetry=telemetry,
            raw_output=parsed,
            error=(
                "Authoritative assessor/result-contract disagreement."
                if contract_disagreement
                else stderr.decode("utf-8", errors="replace").strip() or None
            ),
            fixture=False,
        )

    async def cancel(self, mission_id: str) -> bool:
        process = self._processes.get(mission_id)
        if process is None or process.returncode is not None:
            return False
        process.terminate()
        return True

    @staticmethod
    def _parse_json_output(stdout: str) -> dict[str, Any]:
        try:
            parsed_document = json.loads(stdout.strip())
        except json.JSONDecodeError:
            parsed_document = None
        if isinstance(parsed_document, dict):
            return parsed_document
        for line in reversed(stdout.splitlines()):
            candidate = line.strip()
            if not candidate:
                continue
            try:
                parsed = json.loads(candidate)
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, dict):
                return parsed
        return {"stdout_excerpt": stdout[-4000:]}

    @staticmethod
    def _extract_telemetry(payload: dict[str, Any]) -> TokenTelemetry:
        candidate = payload.get("token_telemetry") or payload.get("telemetry") or {}
        if not isinstance(candidate, dict):
            candidate = {}
        total = candidate.get("total_tokens")
        return TokenTelemetry(
            input_tokens=candidate.get("input_tokens"),
            output_tokens=candidate.get("output_tokens"),
            reasoning_tokens=candidate.get("reasoning_tokens"),
            total_tokens=total,
            estimated_cost_usd=candidate.get("estimated_cost_usd"),
            provider_reported=bool(candidate.get("provider_reported", total is not None)),
        )

    @staticmethod
    def _error_result(
        request: ExecutionRequest,
        started: datetime,
        clock: float,
        message: str,
        exit_code: int | None = None,
    ) -> ExecutionResult:
        return ExecutionResult(
            request_id=request.request_id,
            mission_id=request.mission_id,
            adapter_id="selenium",
            status=ToolStatus.ERROR,
            started_at=started,
            completed_at=_utc_now(),
            duration_ms=max(1, int((monotonic() - clock) * 1000)),
            summary="Selenium adapter could not complete the mission.",
            exit_code=exit_code,
            error=message,
        )
