from typing import Any, Dict, List


def assess_quality(event: Dict[str, Any]) -> Dict[str, Any]:
    persona_output = event.get("interaction", {}).get("persona_output", "")

    response_quality = 1.0
    persona_coherence = 1.0
    violations: List[Dict[str, Any]] = []

    if not persona_output.strip():
        response_quality = 0.0
        persona_coherence = 0.4
        violations.append({
            "violation_id": "V-EMPTY-OUTPUT",
            "violation_type": "coherence_failure",
            "severity": "high",
            "description": "Persona output was empty.",
            "evidence": "persona_output is blank.",
            "recommended_action": "Review persona response generation pipeline."
        })

    elif len(persona_output.strip()) < 20:
        response_quality = 0.5
        violations.append({
            "violation_id": "V-LOW-DETAIL",
            "violation_type": "coherence_failure",
            "severity": "low",
            "description": "Persona output appears unusually short.",
            "evidence": persona_output,
            "recommended_action": "Check whether the persona response adequately addressed the user input."
        })

    return {
        "response_quality": response_quality,
        "persona_coherence": persona_coherence,
        "violations": violations
    }