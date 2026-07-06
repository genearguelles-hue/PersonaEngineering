import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from cognition.agents.concept_formation_agent import ConceptFormationAgent

def main():
    agent = ConceptFormationAgent()

    fragments = [
        "The Ledger stores episodic memory from persona interactions.",
        "The Vector Database stores semantic representations of Ledger fragments.",
        "The Concept Formation Agent retrieves related fragments and synthesizes new ideas.",
        "Persona Engineering enables persistent learning without modifying model weights."
    ]

    for fragment in fragments:
        doc_id = agent.ingest_ledger_fragment(
            fragment,
            {"source": "validation_test"}
        )
        print("Inserted:", doc_id)

    packet = agent.synthesize_concept(
        "How does Persona Engineering create synthetic cognition?"
    )

    print("\n=== SYNTHESIS PACKET ===")
    print(packet)


if __name__ == "__main__":
    main()