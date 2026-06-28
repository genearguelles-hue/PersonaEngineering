from typing import Any, Dict


def assess_primitives(event: Dict[str, Any]) -> Dict[str, Any]:
    active_primitives = event.get("persona_parameters", {}).get("active_primitives", [])

    score = 1.0

    if not active_primitives:
        score = 0.9

    return {
        "score": score,
        "violations": []
    }