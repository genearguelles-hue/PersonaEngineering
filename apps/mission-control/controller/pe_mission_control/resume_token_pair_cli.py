from __future__ import annotations

import argparse
import json
from decimal import Decimal
from pathlib import Path

from .resume_openai_provider import OpenAIResponsesProvider
from .resume_token_pair import PairExperimentConfig, ResumeTokenPairRunner
from .resume_token_telemetry import TokenPricing


def _decimal(value: str | None) -> Decimal | None:
    return Decimal(value) if value is not None else None


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Run one provider-measured governed/ungoverned résumé matched pair."
        )
    )
    parser.add_argument("--pair-id", required=True)
    parser.add_argument("--candidate", required=True, type=Path)
    parser.add_argument("--job", required=True, type=Path)
    parser.add_argument("--persona", required=True, type=Path)
    parser.add_argument("--output-root", required=True, type=Path)
    parser.add_argument("--external-data-consent-id", required=True)
    parser.add_argument("--model", default="gpt-5.6")
    parser.add_argument("--reasoning-effort", default="low")
    parser.add_argument("--max-output-tokens", type=int, default=4000)
    parser.add_argument(
        "--order",
        choices=("auto", "governed-first", "ungoverned-first"),
        default="auto",
    )
    parser.add_argument("--no-repair", action="store_true")
    parser.add_argument("--input-price-per-million")
    parser.add_argument("--cached-input-price-per-million")
    parser.add_argument("--cache-write-input-price-per-million")
    parser.add_argument("--output-price-per-million")
    parser.add_argument("--pricing-source")
    args = parser.parse_args()

    pricing = TokenPricing(
        input_per_million=_decimal(args.input_price_per_million),
        cached_input_per_million=_decimal(args.cached_input_price_per_million),
        cache_write_input_per_million=_decimal(
            args.cache_write_input_price_per_million
        ),
        output_per_million=_decimal(args.output_price_per_million),
        source=args.pricing_source,
    )
    provider = OpenAIResponsesProvider(
        model=args.model,
        reasoning_effort=args.reasoning_effort,
        max_output_tokens=args.max_output_tokens,
        pricing=pricing,
    )
    config = PairExperimentConfig(
        pair_id=args.pair_id,
        candidate_path=args.candidate.expanduser().resolve(),
        job_path=args.job.expanduser().resolve(),
        persona_path=args.persona.expanduser().resolve(),
        output_root=args.output_root.expanduser().resolve(),
        external_data_consent_id=args.external_data_consent_id,
        order=args.order,
        allow_repair=not args.no_repair,
    )
    result = ResumeTokenPairRunner(provider, config).run()
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
