from typing import Any, Dict, List


def assess_drift(event: Dict[str, Any]) -> Dict[str, Any]:
    persona_output = event.get("interaction", {}).get("persona_output", "").lower()

    drift_risk = 0.0
    persona_coherence_adjustment = 1.0
    violations: List[Dict[str, Any]] = []

    if "as an ai language model" in persona_output:
        drift_risk = 0.3
        persona_coherence_adjustment = 0.8
        violations.append({
            "violation_id": "V-GENERIC-MODEL-VOICE",
            "violation_type": "drift_signal",
            "severity": "low",
            "description": "Response may have drifted into generic model voice.",
            "evidence": "as an ai language model",
            "recommended_action": "Check whether persona identity is being preserved."
        })

    return {
        "drift_risk": drift_risk,
        "persona_coherence_adjustment": persona_coherence_adjustment,
        "violations": violations
    }