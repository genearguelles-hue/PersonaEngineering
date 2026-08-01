from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from pe_mission_control.resume_openai_provider import (
    ModelCallResult,
    OpenAIResponsesProvider,
)
from pe_mission_control.resume_token_pair import (
    PairExperimentConfig,
    ResumeTokenPairRunner,
)
from pe_mission_control.resume_token_telemetry import ProviderTokenUsage
from pe_mission_control.resume_token_telemetry import (
    TokenTelemetryError,
    normalize_openai_usage,
)


class FakeProvider:
    model = "test-model"
    reasoning_effort = "low"
    max_output_tokens = 1000

    def __init__(self, *, repair: bool = False):
        self.repair = repair
        self.calls: list[str] = []

    def preflight(self) -> None:
        return None

    def generate(
        self,
        *,
        pair_id: str,
        arm: str,
        call_id: str,
        call_category: str,
        instructions: str,
        prompt: str,
        output_schema: dict | None = None,
    ) -> ModelCallResult:
        self.calls.append(call_id)
        if call_id == "governance-plan-r0":
            text = "Use only authorized evidence."
            tokens = (100, 20)
        elif call_id == "governed-task-r0":
            text = "# Test Candidate\n\n## Experience\nBuilt Python automation."
            tokens = (200, 50)
        elif call_id == "governance-review-r0":
            verdict = "revise" if self.repair else "pass"
            text = json.dumps(
                {
                    "verdict": verdict,
                    "unsupported_claims": [],
                    "missing_required_coverage": [],
                    "repair_instructions": ["Clarify evidence"] if self.repair else [],
                }
            )
            tokens = (120, 30)
        elif call_id == "governed-repair-r1":
            text = "# Test Candidate\n\n## Experience\nBuilt source-backed Python automation."
            tokens = (180, 45)
        elif call_id == "governance-review-r1":
            text = json.dumps(
                {
                    "verdict": "pass",
                    "unsupported_claims": [],
                    "missing_required_coverage": [],
                    "repair_instructions": [],
                }
            )
            tokens = (125, 25)
        elif call_id == "ungoverned-task-r0":
            text = "# Test Candidate\n\nPython automation professional."
            tokens = (170, 40)
        elif call_id == "blind-quality-evaluation-r0":
            text = json.dumps(
                {
                    "A": {
                        "quality_score": 0.9,
                        "evidence_fidelity_score": 1.0,
                        "job_relevance_score": 0.8,
                        "unsupported_claim_count": 0,
                        "findings": [],
                    },
                    "B": {
                        "quality_score": 0.7,
                        "evidence_fidelity_score": 0.8,
                        "job_relevance_score": 0.6,
                        "unsupported_claim_count": 0,
                        "findings": [],
                    },
                }
            )
            tokens = (300, 60)
        else:
            raise AssertionError(call_id)
        input_tokens, output_tokens = tokens
        telemetry = ProviderTokenUsage(
            schema_version="pe.resume-provider-token-usage.v1",
            pair_id=pair_id,
            arm=arm,
            call_id=call_id,
            call_category=call_category,
            included_in_primary_total=call_category != "evaluation",
            provider="openai",
            provider_reported=True,
            response_id=f"response-{call_id}",
            model=self.model,
            input_tokens=input_tokens,
            cached_input_tokens=0,
            cache_write_input_tokens=0,
            output_tokens=output_tokens,
            reasoning_tokens=0,
            total_tokens=input_tokens + output_tokens,
            latency_ms=10,
            retry_count=0,
            estimated_cost_usd=None,
            prompt_sha256=hashlib.sha256(prompt.encode()).hexdigest(),
            output_sha256=hashlib.sha256(text.encode()).hexdigest(),
        )
        return ModelCallResult(text=text, telemetry=telemetry)


class ResumeTokenComparisonTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.candidate = self.root / "candidate.json"
        self.job = self.root / "job.json"
        self.persona = self.root / "persona.json"
        self._write(
            self.candidate,
            {
                "candidate": {"display_name": "Private Candidate Name"},
                "skills": ["Python automation"],
                "experience": [],
            },
        )
        self._write(
            self.job,
            {
                "employer": "Private Target Employer",
                "role_title": "AI Automation Engineer",
                "requirements": [
                    {"id": "r1", "text": "Build Python automation", "required": True}
                ],
            },
        )
        self._write(
            self.persona,
            {
                "id": "pe.resume_tailoring_specialist",
                "version": "0.1.0",
                "mission": "Evidence-bound tailoring",
                "axioms": [{"id": "A1", "statement": "Do not invent claims"}],
                "primitives": [{"id": "P1", "name": "Evidence mapping"}],
                "runtime_contract": {"persona_model": "Pi = <E, P, A>"},
            },
        )

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_primary_comparison_excludes_blind_evaluator(self) -> None:
        runner = ResumeTokenPairRunner(FakeProvider(), self._config("pair-no-repair-001"))
        result = runner.run()
        comparison = result["comparison"]
        self.assertEqual(comparison["governed"]["total_tokens"], 520)
        self.assertEqual(comparison["ungoverned"]["total_tokens"], 210)
        self.assertEqual(comparison["evaluation"]["total_tokens"], 360)
        self.assertEqual(comparison["token_delta"], -310)
        self.assertTrue(comparison["evaluation_excluded_from_primary_totals"])
        self.assertTrue(result["ledger"]["valid"])
        self.assertEqual(
            comparison["governed"]["tokens_by_category"],
            {"governance": 270, "task": 250},
        )

    def test_repair_tokens_are_exposed_and_ledger_omits_private_text(self) -> None:
        pair_id = "pair-with-repair-001"
        runner = ResumeTokenPairRunner(
            FakeProvider(repair=True), self._config(pair_id)
        )
        result = runner.run()
        comparison = result["comparison"]
        self.assertTrue(comparison["governed_repair_performed"])
        self.assertEqual(comparison["governed"]["tokens_by_category"]["repair"], 225)
        events = (
            self.root / "runs" / "missions" / pair_id / "events.jsonl"
        ).read_text(encoding="utf-8")
        self.assertNotIn("Private Candidate Name", events)
        self.assertNotIn("Private Target Employer", events)
        self.assertTrue(result["ledger"]["valid"])

    def test_openai_usage_is_canonical_and_reasoning_is_not_double_counted(self) -> None:
        telemetry = normalize_openai_usage(
            pair_id="pair-usage-001",
            arm="governed",
            call_id="task-r0",
            call_category="task",
            response={
                "id": "resp_test",
                "model": "test-model-2026-07-31",
                "usage": {
                    "input_tokens": 100,
                    "input_tokens_details": {
                        "cached_tokens": 20,
                        "cache_write_tokens": 5,
                    },
                    "output_tokens": 40,
                    "output_tokens_details": {"reasoning_tokens": 30},
                    "total_tokens": 140,
                },
            },
            latency_ms=9,
            retry_count=0,
            prompt_sha256="a" * 64,
            output_sha256="b" * 64,
        )
        self.assertEqual(telemetry.total_tokens, 140)
        self.assertEqual(telemetry.reasoning_tokens, 30)
        self.assertEqual(telemetry.cache_write_input_tokens, 5)

    def test_missing_provider_usage_fails_closed(self) -> None:
        with self.assertRaises(TokenTelemetryError):
            normalize_openai_usage(
                pair_id="pair-usage-missing-001",
                arm="ungoverned",
                call_id="task-r0",
                call_category="task",
                response={"id": "resp_test", "model": "test-model"},
                latency_ms=9,
                retry_count=0,
                prompt_sha256="a" * 64,
                output_sha256="b" * 64,
            )

    def test_provider_sets_store_false_and_structured_output(self) -> None:
        captured: dict = {}

        def transport(url: str, headers: dict, body: bytes, timeout: int) -> dict:
            captured.update(json.loads(body))
            return {
                "id": "resp_structured",
                "model": "test-model",
                "status": "completed",
                "output_text": '{"verdict":"pass"}',
                "usage": {
                    "input_tokens": 20,
                    "input_tokens_details": {
                        "cached_tokens": 0,
                        "cache_write_tokens": 0,
                    },
                    "output_tokens": 5,
                    "output_tokens_details": {"reasoning_tokens": 0},
                    "total_tokens": 25,
                },
            }

        provider = OpenAIResponsesProvider(
            model="test-model",
            reasoning_effort="low",
            max_output_tokens=256,
            api_key="test-key-not-real",
            transport=transport,
        )
        provider.generate(
            pair_id="pair-structured-001",
            arm="governed",
            call_id="review-r0",
            call_category="governance",
            instructions="Return JSON",
            prompt="Review",
            output_schema={
                "type": "object",
                "additionalProperties": False,
                "required": ["verdict"],
                "properties": {"verdict": {"const": "pass"}},
            },
        )
        self.assertIs(captured["store"], False)
        self.assertEqual(captured["text"]["format"]["type"], "json_schema")
        self.assertIs(captured["text"]["format"]["strict"], True)

    def _config(self, pair_id: str) -> PairExperimentConfig:
        return PairExperimentConfig(
            pair_id=pair_id,
            candidate_path=self.candidate,
            job_path=self.job,
            persona_path=self.persona,
            output_root=self.root / "runs",
            external_data_consent_id="consent-test-001",
            order="governed-first",
        )

    @staticmethod
    def _write(path: Path, value: dict) -> None:
        path.write_text(json.dumps(value), encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
