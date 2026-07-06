from typing import Any, Dict


CHARS_PER_TOKEN_ESTIMATE = 4


def estimate_tokens(text: str) -> int:
    if not text:
        return 0

    return max(1, round(len(text) / CHARS_PER_TOKEN_ESTIMATE))


def assess_token_economics(event: Dict[str, Any]) -> Dict[str, Any]:
    interaction = event.get("interaction", {})

    user_input = interaction.get("user_input", "")
    persona_output = interaction.get("persona_output", "")
    context_summary = interaction.get("context_summary", "")

    input_tokens = estimate_tokens(user_input + "\n" + context_summary)
    output_tokens = estimate_tokens(persona_output)
    total_tokens = input_tokens + output_tokens

    baseline_tokens = estimate_tokens(
        user_input
        + "\n"
        + context_summary
        + "\n"
        + persona_output
        + "\n"
        + "Unstructured interaction without persona-guided constraints, assessment, or reusable context."
    )

    estimated_token_savings = max(0, baseline_tokens - total_tokens)

    savings_ratio = 0.0

    if baseline_tokens > 0:
        savings_ratio = round(estimated_token_savings / baseline_tokens, 3)

    return {
        "input_token_estimate": input_tokens,
        "output_token_estimate": output_tokens,
        "total_token_estimate": total_tokens,
        "baseline_token_estimate": baseline_tokens,
        "estimated_token_savings": estimated_token_savings,
        "estimated_savings_ratio": savings_ratio,
        "estimation_method": "character_count_approximation",
        "chars_per_token_estimate": CHARS_PER_TOKEN_ESTIMATE
    }