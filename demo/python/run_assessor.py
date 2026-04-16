import os
import sys

CURRENT_DIR = os.path.dirname(__file__)
REPO_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, "..", ".."))
CODEBASE_DIR = os.path.join(REPO_ROOT, "codebase")

if CODEBASE_DIR not in sys.path:
    sys.path.append(CODEBASE_DIR)

from assessor import Assessor


if __name__ == "__main__":
    ledger_path = os.path.join(REPO_ROOT, "demo", "python", "persona_ledger.json")

    assessor = Assessor()
    report = assessor.assess(ledger_path)

    print("\n=== Assessor Report ===")
    print("Ledger valid:", report.ledger_valid)
    print("Total entries:", report.total_entries)
    print("Max axiom pressure:", report.max_axiom_pressure)
    print("Max primitive saturation:", report.max_primitive_saturation)
    print("Drift warnings:", report.drift_warnings)
    print("Stable entries:", report.stable_entries)
    print("Persona valid:", report.persona_valid)
    print("Summary:", report.summary)