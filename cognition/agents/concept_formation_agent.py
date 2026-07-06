# agents/concept_formation_agent.py

import chromadb
from sentence_transformers import SentenceTransformer
from datetime import datetime
import uuid

class ConceptFormationAgent:
    def __init__(self, db_path="cognition_module/vdb/chroma_store"):
        self.client = chromadb.PersistentClient(path=db_path)
        self.collection = self.client.get_or_create_collection("ledger_concepts")
        self.embedder = SentenceTransformer("all-MiniLM-L6-v2")

    def ingest_ledger_fragment(self, text, metadata=None):
        doc_id = str(uuid.uuid4())
        embedding = self.embedder.encode(text).tolist()

        self.collection.add(
            ids=[doc_id],
            documents=[text],
            embeddings=[embedding],
            metadatas=[metadata or {}]
        )

        return doc_id

    def retrieve_relevant_fragments(self, query, n_results=8):
        query_embedding = self.embedder.encode(query).tolist()

        return self.collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results
        )

    def synthesize_concept(self, query):
        results = self.retrieve_relevant_fragments(query)

        fragments = results.get("documents", [[]])[0]

        synthesis_packet = {
            "event_type": "concept_synthesis",
            "schema_version": "0.1",
            "event_id": str(uuid.uuid4()),
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "agent": "concept_formation_agent",
            "query": query,
            "source_fragments": fragments,
            "synthesis_prompt": self._build_synthesis_prompt(query, fragments)
        }

        return synthesis_packet

    def _build_synthesis_prompt(self, query, fragments):
        joined = "\n\n".join(f"- {f}" for f in fragments)

        return f"""
Human request:
{query}

Relevant Ledger fragments:
{joined}

Task:
Synthesize a novel concept, hypothesis, or interpretation from these fragments.
Identify:
1. Core pattern
2. Tension or contradiction
3. Emerging concept
4. Practical application
5. Confidence level
"""