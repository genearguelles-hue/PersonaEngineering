from typing import Any, Dict


def assess_engrams(event: Dict[str, Any]) -> Dict[str, Any]:
    active_engrams = event.get("persona_parameters", {}).get("active_engrams", [])

    return {
        "engram_count": len(active_engrams),
        "violations": []
    }