from typing import Any, Dict, List


def assess_governance(violations: List[Dict[str, Any]]) -> Dict[str, Any]:
    severities = [violation.get("severity", "low") for violation in violations]

    if "critical" in severities:
        return {
            "action_taken": "escalate",
            "human_review_required": True,
            "review_status": "pending",
            "governance_notes": "Critical violation detected. Human review required."
        }

    if "high" in severities:
        return {
            "action_taken": "warn",
            "human_review_required": True,
            "review_status": "pending",
            "governance_notes": "High severity violation detected. Human review recommended."
        }

    if "medium" in severities:
        return {
            "action_taken": "warn",
            "human_review_required": False,
            "review_status": "not_required",
            "governance_notes": "Medium severity violation detected. Warning recorded."
        }

    return {
        "action_taken": "none",
        "human_review_required": False,
        "review_status": "not_required",
        "governance_notes": "No governance intervention required."
    }