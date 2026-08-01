from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol

from .ledger import MissionLedger
from .resume_openai_provider import ModelCallResult, ResumeProviderError
from .resume_token_telemetry import ProviderTokenUsage, aggregate_usage


class PairExperimentError(RuntimeError):
    """Raised when the matched-pair experiment cannot produce valid evidence."""


class TextProvider(Protocol):
    model: str
    reasoning_effort: str
    max_output_tokens: int

    def preflight(self) -> None: ...

    def generate(
        self,
        *,
        pair_id: str,
        arm: str,
        call_id: str,
        call_category: str,
        instructions: str,
        prompt: str,
        output_schema: dict[str, Any] | None = None,
    ) -> ModelCallResult: ...


@dataclass(frozen=True)
class PairExperimentConfig:
    pair_id: str
    candidate_path: Path
    job_path: Path
    persona_path: Path
    output_root: Path
    external_data_consent_id: str
    order: str = "auto"
    allow_repair: bool = True


class ResumeTokenPairRunner:
    """Runs and seals one controlled governed/ungoverned résumé pair."""

    def __init__(self, provider: TextProvider, config: PairExperimentConfig):
        self.provider = provider
        self.config = config
        self.run_root = config.output_root / "missions" / config.pair_id
        self.ledger = MissionLedger(config.output_root)
        self.telemetry: list[ProviderTokenUsage] = []

    def run(self) -> dict[str, Any]:
        self._preflight()
        candidate = self._load_object(self.config.candidate_path)
        job = self._load_object(self.config.job_path)
        persona = self._load_object(self.config.persona_path)
        source_hashes = {
            "candidate_sha256": self._file_hash(self.config.candidate_path),
            "job_sha256": self._file_hash(self.config.job_path),
            "persona_sha256": self._file_hash(self.config.persona_path),
        }
        shared_prompt = self._shared_task_prompt(candidate, job)
        persona_contract = self._persona_contract(persona)
        order = self._resolve_order()
        self._append(
            "resume_token_pair_received",
            "received",
            {
                "pair_id": self.config.pair_id,
                "model": self.provider.model,
                "reasoning_effort": self.provider.reasoning_effort,
                "max_output_tokens": self.provider.max_output_tokens,
                "execution_order": order,
                "source_hashes": source_hashes,
            },
        )
        self._append(
            "resume_token_pair_authorized",
            "authorized",
            {
                "decision": "AUTHORIZED",
                "external_model_calls": True,
                "provider": "openai",
                "provider_store": False,
                "external_submission": False,
                "production_vector_write": False,
                "consent_record_hash": self._sha256_text(
                    self.config.external_data_consent_id
                ),
                "policy_bindings": [
                    "PE-RESUME-TOKEN-MATCHED-PAIR-v1",
                    "PE-RESUME-EXTERNAL-MODEL-CONSENT-v1",
                    "PE-RESUME-NO-EXTERNAL-SUBMISSION",
                ],
            },
        )
        results: dict[str, dict[str, Any]] = {}
        try:
            for arm in order:
                self._append(
                    "resume_token_arm_started",
                    "running",
                    {"arm": arm},
                )
                if arm == "governed":
                    results[arm] = self._run_governed(
                        shared_prompt=shared_prompt,
                        persona_contract=persona_contract,
                        candidate=candidate,
                        job=job,
                        source_hashes=source_hashes,
                    )
                else:
                    results[arm] = self._run_ungoverned(shared_prompt)
                self._append(
                    "resume_token_arm_completed",
                    "running",
                    {
                        "arm": arm,
                        "output_sha256": self._sha256_text(results[arm]["resume"]),
                        "call_count": len(
                            [item for item in self.telemetry if item.arm == arm]
                        ),
                    },
                )
            quality = self._blind_evaluate(
                candidate=candidate,
                job=job,
                governed=results["governed"]["resume"],
                ungoverned=results["ungoverned"]["resume"],
            )
            comparison = self._compare(results, quality, source_hashes, order)
            self._write_artifacts(results, quality, comparison)
            self._append(
                "resume_token_pair_compared",
                "running",
                {
                    "comparison_sha256": self._sha256_json(comparison),
                    "governed_total_tokens": comparison["governed"]["total_tokens"],
                    "ungoverned_total_tokens": comparison["ungoverned"]["total_tokens"],
                    "token_delta": comparison["token_delta"],
                    "token_change_percent": comparison["token_change_percent"],
                    "quality_result_hash": self._sha256_json(quality),
                },
            )
            self._append(
                "resume_token_pair_terminal",
                "completed",
                {
                    "status": "completed",
                    "provider_reported": True,
                    "external_submission": False,
                    "claim_scope": "single matched pair; no population-level savings claim",
                },
            )
            manifest = self.ledger.seal_manifest(self.config.pair_id)
            verification = self.ledger.verify(self.config.pair_id)
            return {
                "comparison": comparison,
                "ledger": verification,
                "manifest_hash": manifest["manifest_hash"],
                "run_directory": str(self.run_root),
            }
        except Exception as exc:
            self._append(
                "resume_token_pair_terminal",
                "failed",
                {
                    "status": "failed",
                    "error_type": type(exc).__name__,
                    "error_hash": self._sha256_text(str(exc)),
                    "external_submission": False,
                },
            )
            self._write_telemetry()
            self.ledger.seal_manifest(self.config.pair_id)
            if isinstance(exc, (PairExperimentError, ResumeProviderError)):
                raise
            raise PairExperimentError(str(exc)) from exc

    def _run_ungoverned(self, shared_prompt: str) -> dict[str, Any]:
        result = self._call(
            arm="ungoverned",
            call_id="ungoverned-task-r0",
            category="task",
            instructions=(
                "Generate the requested résumé. Return Markdown only. "
                "Do not discuss your process."
            ),
            prompt=shared_prompt,
        )
        return {"resume": result.text, "review": None, "repair_performed": False}

    def _run_governed(
        self,
        *,
        shared_prompt: str,
        persona_contract: dict[str, Any],
        candidate: dict[str, Any],
        job: dict[str, Any],
        source_hashes: dict[str, str],
    ) -> dict[str, Any]:
        persona_text = json.dumps(persona_contract, sort_keys=True, ensure_ascii=False)
        plan = self._call(
            arm="governed",
            call_id="governance-plan-r0",
            category="governance",
            instructions=(
                "Act as the bound Resume Tailoring Specialist persona. Create a concise "
                "evidence-control plan for the downstream résumé generator. Do not draft "
                "the résumé. Preserve every axiom and return plain text."
            ),
            prompt=(
                f"PERSONA CONTRACT\n{persona_text}\n\n"
                f"SOURCE HASHES\n{json.dumps(source_hashes, sort_keys=True)}\n\n"
                f"CANDIDATE PROFILE\n{json.dumps(candidate, sort_keys=True, ensure_ascii=False)}\n\n"
                f"TARGET JOB\n{json.dumps(job, sort_keys=True, ensure_ascii=False)}"
            ),
        )
        draft = self._call(
            arm="governed",
            call_id="governed-task-r0",
            category="task",
            instructions=(
                "Act as pe.resume_tailoring_specialist. Follow the supplied governance "
                "plan. Use only authorized evidence, never inflate adjacent experience, "
                "and return Markdown only without process commentary."
            ),
            prompt=f"GOVERNANCE PLAN\n{plan.text}\n\n{shared_prompt}",
        )
        review = self._review(
            candidate=candidate,
            job=job,
            resume=draft.text,
            call_id="governance-review-r0",
        )
        final_text = draft.text
        repair_performed = False
        if review["verdict"] == "revise" and self.config.allow_repair:
            repair = self._call(
                arm="governed",
                call_id="governed-repair-r1",
                category="repair",
                instructions=(
                    "Act as pe.resume_tailoring_specialist. Repair the résumé using only "
                    "the authorized sources and reviewer instructions. Remove unsupported "
                    "claims rather than inventing evidence. Return Markdown only."
                ),
                prompt=(
                    f"AUTHORIZED CANDIDATE PROFILE\n{json.dumps(candidate, sort_keys=True, ensure_ascii=False)}\n\n"
                    f"TARGET JOB\n{json.dumps(job, sort_keys=True, ensure_ascii=False)}\n\n"
                    f"CURRENT RÉSUMÉ\n{draft.text}\n\n"
                    f"REVIEW\n{json.dumps(review, sort_keys=True, ensure_ascii=False)}"
                ),
            )
            final_text = repair.text
            repair_performed = True
            review = self._review(
                candidate=candidate,
                job=job,
                resume=final_text,
                call_id="governance-review-r1",
            )
        return {
            "resume": final_text,
            "review": review,
            "repair_performed": repair_performed,
            "application_ready": review["verdict"] == "pass",
        }

    def _review(
        self,
        *,
        candidate: dict[str, Any],
        job: dict[str, Any],
        resume: str,
        call_id: str,
    ) -> dict[str, Any]:
        result = self._call(
            arm="governed",
            call_id=call_id,
            category="governance",
            instructions=(
                "You are the independent Persona Assessor, not the résumé persona. "
                "Evaluate claims only against authorized evidence. Return one JSON object "
                "with keys verdict, unsupported_claims, missing_required_coverage, and "
                "repair_instructions. verdict must be pass or revise. No Markdown."
            ),
            prompt=(
                f"AUTHORIZED CANDIDATE PROFILE\n{json.dumps(candidate, sort_keys=True, ensure_ascii=False)}\n\n"
                f"TARGET JOB\n{json.dumps(job, sort_keys=True, ensure_ascii=False)}\n\n"
                f"RÉSUMÉ UNDER REVIEW\n{resume}"
            ),
            output_schema=self._review_schema(),
        )
        value = self._parse_json_object(result.text, call_id)
        if value.get("verdict") not in {"pass", "revise"}:
            raise PairExperimentError(f"{call_id} returned invalid verdict")
        for key in (
            "unsupported_claims",
            "missing_required_coverage",
            "repair_instructions",
        ):
            if not isinstance(value.get(key), list):
                raise PairExperimentError(f"{call_id} omitted list field {key}")
        return value

    def _blind_evaluate(
        self,
        *,
        candidate: dict[str, Any],
        job: dict[str, Any],
        governed: str,
        ungoverned: str,
    ) -> dict[str, Any]:
        governed_is_a = int(self._sha256_text(self.config.pair_id)[-1], 16) % 2 == 0
        outputs = {
            "A": governed if governed_is_a else ungoverned,
            "B": ungoverned if governed_is_a else governed,
        }
        result = self._call(
            arm="comparison",
            call_id="blind-quality-evaluation-r0",
            category="evaluation",
            instructions=(
                "You are an independent blind résumé evaluator. The two candidates are "
                "alternative outputs from the same authorized evidence. Do not infer how "
                "either was produced. Return one JSON object with keys A and B. Each must "
                "contain quality_score (0 to 1), evidence_fidelity_score (0 to 1), "
                "job_relevance_score (0 to 1), unsupported_claim_count (integer), and "
                "findings (array of short strings). No Markdown."
            ),
            prompt=(
                f"AUTHORIZED CANDIDATE PROFILE\n{json.dumps(candidate, sort_keys=True, ensure_ascii=False)}\n\n"
                f"TARGET JOB\n{json.dumps(job, sort_keys=True, ensure_ascii=False)}\n\n"
                f"OUTPUT A\n{outputs['A']}\n\nOUTPUT B\n{outputs['B']}"
            ),
            output_schema=self._quality_schema(),
        )
        blind = self._parse_json_object(result.text, "blind-quality-evaluation-r0")
        for label in ("A", "B"):
            self._validate_quality(blind.get(label), label)
        mapped = {
            "schema_version": "pe.resume-blind-quality-assessment.v1",
            "evaluator_call_id": "blind-quality-evaluation-r0",
            "blind_assignment": {
                "governed": "A" if governed_is_a else "B",
                "ungoverned": "B" if governed_is_a else "A",
            },
            "governed": blind["A" if governed_is_a else "B"],
            "ungoverned": blind["B" if governed_is_a else "A"],
        }
        return mapped

    def _compare(
        self,
        results: dict[str, dict[str, Any]],
        quality: dict[str, Any],
        source_hashes: dict[str, str],
        order: list[str],
    ) -> dict[str, Any]:
        # T_governed = T_task + T_governance + T_repair.
        # Blind evaluation is measured separately and excluded from both arms.
        governed = aggregate_usage(self.telemetry, arm="governed")
        ungoverned = aggregate_usage(self.telemetry, arm="ungoverned")
        if not governed["provider_reported"] or not ungoverned["provider_reported"]:
            raise PairExperimentError("both arms require provider-reported usage")
        delta = ungoverned["total_tokens"] - governed["total_tokens"]
        percent = (
            round(delta / ungoverned["total_tokens"] * 100, 4)
            if ungoverned["total_tokens"]
            else None
        )
        governed_quality = quality["governed"]["quality_score"]
        ungoverned_quality = quality["ungoverned"]["quality_score"]
        return {
            "schema_version": "pe.resume-token-comparison.v1",
            "pair_id": self.config.pair_id,
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "mission_class": "resume_tailoring",
            "model": self.provider.model,
            "reasoning_effort": self.provider.reasoning_effort,
            "max_output_tokens": self.provider.max_output_tokens,
            "execution_order": order,
            "source_hashes": source_hashes,
            "governed": governed,
            "ungoverned": ungoverned,
            "evaluation": aggregate_usage(
                self.telemetry, arm="comparison", include_evaluation=True
            ),
            "evaluation_excluded_from_primary_totals": True,
            "token_delta": delta,
            "token_change_percent": percent,
            "interpretation": (
                "positive means the governed arm used fewer tokens; negative means it used more"
            ),
            "governed_quality_score": governed_quality,
            "ungoverned_quality_score": ungoverned_quality,
            "quality_delta": round(governed_quality - ungoverned_quality, 4),
            "governed_tokens_per_quality_point": self._tokens_per_quality(
                governed["total_tokens"], governed_quality
            ),
            "ungoverned_tokens_per_quality_point": self._tokens_per_quality(
                ungoverned["total_tokens"], ungoverned_quality
            ),
            "governed_repair_performed": results["governed"]["repair_performed"],
            "governed_application_ready": results["governed"].get(
                "application_ready", False
            ),
            "claim_scope": "single matched pair; mechanism proof only",
        }

    def _call(
        self,
        *,
        arm: str,
        call_id: str,
        category: str,
        instructions: str,
        prompt: str,
        output_schema: dict[str, Any] | None = None,
    ) -> ModelCallResult:
        result = self.provider.generate(
            pair_id=self.config.pair_id,
            arm=arm,
            call_id=call_id,
            call_category=category,
            instructions=instructions,
            prompt=prompt,
            output_schema=output_schema,
        )
        if not result.telemetry.provider_reported:
            raise PairExperimentError(f"{call_id} lacks provider-reported usage")
        self.telemetry.append(result.telemetry)
        self._write_telemetry()
        self._append(
            "resume_provider_call_completed",
            "running",
            {
                "arm": arm,
                "call_id": call_id,
                "call_category": category,
                "included_in_primary_total": result.telemetry.included_in_primary_total,
                "provider": result.telemetry.provider,
                "provider_reported": True,
                "response_id_hash": self._sha256_text(result.telemetry.response_id),
                "model": result.telemetry.model,
                "input_tokens": result.telemetry.input_tokens,
                "cached_input_tokens": result.telemetry.cached_input_tokens,
                "cache_write_input_tokens": result.telemetry.cache_write_input_tokens,
                "output_tokens": result.telemetry.output_tokens,
                "reasoning_tokens": result.telemetry.reasoning_tokens,
                "total_tokens": result.telemetry.total_tokens,
                "latency_ms": result.telemetry.latency_ms,
                "retry_count": result.telemetry.retry_count,
                "estimated_cost_usd": result.telemetry.estimated_cost_usd,
                "prompt_sha256": result.telemetry.prompt_sha256,
                "output_sha256": result.telemetry.output_sha256,
            },
        )
        return result

    def _write_artifacts(
        self,
        results: dict[str, dict[str, Any]],
        quality: dict[str, Any],
        comparison: dict[str, Any],
    ) -> None:
        governed_dir = self.run_root / "arms" / "governed"
        ungoverned_dir = self.run_root / "arms" / "ungoverned"
        governed_dir.mkdir(parents=True, exist_ok=True)
        ungoverned_dir.mkdir(parents=True, exist_ok=True)
        (governed_dir / "resume.md").write_text(
            results["governed"]["resume"].rstrip() + "\n", encoding="utf-8"
        )
        (ungoverned_dir / "resume.md").write_text(
            results["ungoverned"]["resume"].rstrip() + "\n", encoding="utf-8"
        )
        self._write_json(governed_dir / "persona-review.json", results["governed"]["review"])
        self._write_json(self.run_root / "blind-quality-assessment.json", quality)
        self._write_json(self.run_root / "comparison.json", comparison)
        (self.run_root / "COMPARISON_REPORT.md").write_text(
            self._report(comparison), encoding="utf-8"
        )
        self._write_telemetry()

    def _report(self, comparison: dict[str, Any]) -> str:
        g = comparison["governed"]
        u = comparison["ungoverned"]
        direction = "fewer" if comparison["token_delta"] >= 0 else "more"
        amount = abs(comparison["token_delta"])
        return f"""# Résumé Token-Governance Matched Pair

Pair: `{comparison['pair_id']}`

Model: `{comparison['model']}`

Execution order: `{' -> '.join(comparison['execution_order'])}`

Evidence status: provider-reported usage for every call

| Measure | Governed | Ungoverned |
|---|---:|---:|
| Input tokens | {g['input_tokens']} | {u['input_tokens']} |
| Output tokens | {g['output_tokens']} | {u['output_tokens']} |
| Reasoning tokens (included in output) | {g['reasoning_tokens']} | {u['reasoning_tokens']} |
| Total tokens | {g['total_tokens']} | {u['total_tokens']} |
| Calls | {g['call_count']} | {u['call_count']} |
| Quality score | {comparison['governed_quality_score']:.3f} | {comparison['ungoverned_quality_score']:.3f} |

The governed arm used **{amount} {direction} tokens** than the ungoverned arm.
The signed change is **{comparison['token_change_percent']}%**; positive means
governance saved tokens and negative means governance consumed more.

Governed category totals: `{json.dumps(g['tokens_by_category'], sort_keys=True)}`.
Blind-evaluation tokens were monitored separately and excluded from both primary totals.

This is one matched pair and proves the measurement mechanism only. It does not establish
statistically reliable token savings.
"""

    def _preflight(self) -> None:
        if len(self.config.pair_id) < 8:
            raise PairExperimentError("pair_id must contain at least eight characters")
        if len(self.config.external_data_consent_id) < 8:
            raise PairExperimentError("external data consent id is required")
        for path in (
            self.config.candidate_path,
            self.config.job_path,
            self.config.persona_path,
        ):
            if not path.is_file() or path.is_symlink():
                raise PairExperimentError(f"required regular source file missing: {path}")
        if self.run_root.exists():
            raise PairExperimentError(f"pair output already exists: {self.run_root}")
        self.provider.preflight()
        persona = self._load_object(self.config.persona_path)
        if persona.get("id") != "pe.resume_tailoring_specialist":
            raise PairExperimentError("unexpected persona id")
        contract = persona.get("runtime_contract") or {}
        if contract.get("persona_model") != "Pi = <E, P, A>":
            raise PairExperimentError("persona model contract mismatch")
        job = self._load_object(self.config.job_path)
        if not isinstance(job.get("requirements"), list) or not job["requirements"]:
            raise PairExperimentError("job source requires a non-empty requirements array")

    def _resolve_order(self) -> list[str]:
        if self.config.order == "governed-first":
            return ["governed", "ungoverned"]
        if self.config.order == "ungoverned-first":
            return ["ungoverned", "governed"]
        if self.config.order != "auto":
            raise PairExperimentError(f"unsupported execution order: {self.config.order}")
        even = int(self._sha256_text(self.config.pair_id)[0], 16) % 2 == 0
        return ["governed", "ungoverned"] if even else ["ungoverned", "governed"]

    @staticmethod
    def _shared_task_prompt(candidate: dict[str, Any], job: dict[str, Any]) -> str:
        return (
            "TASK\nCreate an ATS-readable résumé tailored to the target job. Use only "
            "facts in the candidate profile. Preserve contact details. Separate direct "
            "experience from transferable experience. Do not invent metrics, tools, legal "
            "experience, case-management experience, titles, dates, credentials, or outcomes. "
            "Return a complete Markdown résumé.\n\n"
            f"CANDIDATE PROFILE\n{json.dumps(candidate, sort_keys=True, ensure_ascii=False)}\n\n"
            f"TARGET JOB\n{json.dumps(job, sort_keys=True, ensure_ascii=False)}"
        )

    @staticmethod
    def _persona_contract(persona: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": persona.get("id"),
            "version": persona.get("version"),
            "mission": persona.get("mission"),
            "axioms": [
                {"id": item.get("id"), "statement": item.get("statement")}
                for item in persona.get("axioms") or []
            ],
            "primitives": [
                {"id": item.get("id"), "name": item.get("name")}
                for item in persona.get("primitives") or []
            ],
            "runtime_contract": persona.get("runtime_contract"),
        }

    @staticmethod
    def _parse_json_object(text: str, call_id: str) -> dict[str, Any]:
        candidate = text.strip()
        if candidate.startswith("```"):
            lines = candidate.splitlines()
            if lines and lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            candidate = "\n".join(lines).strip()
        try:
            value = json.loads(candidate)
        except json.JSONDecodeError as exc:
            raise PairExperimentError(f"{call_id} did not return valid JSON") from exc
        if not isinstance(value, dict):
            raise PairExperimentError(f"{call_id} must return a JSON object")
        return value

    @staticmethod
    def _validate_quality(value: Any, label: str) -> None:
        if not isinstance(value, dict):
            raise PairExperimentError(f"blind evaluator omitted output {label}")
        for field in (
            "quality_score",
            "evidence_fidelity_score",
            "job_relevance_score",
        ):
            score = value.get(field)
            if not isinstance(score, (int, float)) or isinstance(score, bool) or not 0 <= score <= 1:
                raise PairExperimentError(f"invalid {label}.{field}")
        count = value.get("unsupported_claim_count")
        if not isinstance(count, int) or isinstance(count, bool) or count < 0:
            raise PairExperimentError(f"invalid {label}.unsupported_claim_count")
        if not isinstance(value.get("findings"), list):
            raise PairExperimentError(f"invalid {label}.findings")

    @staticmethod
    def _review_schema() -> dict[str, Any]:
        return {
            "type": "object",
            "additionalProperties": False,
            "required": [
                "verdict",
                "unsupported_claims",
                "missing_required_coverage",
                "repair_instructions",
            ],
            "properties": {
                "verdict": {"type": "string", "enum": ["pass", "revise"]},
                "unsupported_claims": {
                    "type": "array",
                    "items": {"type": "string"},
                },
                "missing_required_coverage": {
                    "type": "array",
                    "items": {"type": "string"},
                },
                "repair_instructions": {
                    "type": "array",
                    "items": {"type": "string"},
                },
            },
        }

    @staticmethod
    def _quality_schema() -> dict[str, Any]:
        score = {"type": "number", "minimum": 0, "maximum": 1}
        output = {
            "type": "object",
            "additionalProperties": False,
            "required": [
                "quality_score",
                "evidence_fidelity_score",
                "job_relevance_score",
                "unsupported_claim_count",
                "findings",
            ],
            "properties": {
                "quality_score": score,
                "evidence_fidelity_score": score,
                "job_relevance_score": score,
                "unsupported_claim_count": {"type": "integer", "minimum": 0},
                "findings": {"type": "array", "items": {"type": "string"}},
            },
        }
        return {
            "type": "object",
            "additionalProperties": False,
            "required": ["A", "B"],
            "properties": {"A": output, "B": output},
        }

    def _append(self, event_type: str, state: str, details: dict[str, Any]) -> None:
        self.ledger.append(self.config.pair_id, event_type, state, details)

    def _write_telemetry(self) -> None:
        if not self.telemetry:
            return
        path = self.run_root / "provider-token-telemetry.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            "".join(
                json.dumps(item.as_dict(), sort_keys=True) + "\n"
                for item in self.telemetry
            ),
            encoding="utf-8",
        )

    @staticmethod
    def _load_object(path: Path) -> dict[str, Any]:
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise PairExperimentError(f"invalid JSON source {path}: {exc}") from exc
        if not isinstance(value, dict):
            raise PairExperimentError(f"expected JSON object: {path}")
        return value

    @staticmethod
    def _write_json(path: Path, value: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    @staticmethod
    def _file_hash(path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()

    @staticmethod
    def _sha256_text(value: str) -> str:
        return hashlib.sha256(value.encode("utf-8")).hexdigest()

    @staticmethod
    def _sha256_json(value: dict[str, Any]) -> str:
        return hashlib.sha256(
            json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        ).hexdigest()

    @staticmethod
    def _tokens_per_quality(tokens: int, score: float) -> float | None:
        return round(tokens / score, 4) if score > 0 else None
