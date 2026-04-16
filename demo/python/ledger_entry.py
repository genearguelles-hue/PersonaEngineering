import hashlib
import json
from dataclasses import dataclass, field
from typing import Dict, List, Any
import time


@dataclass
class LedgerEntry:
    """
    Immutable record of a single persona interaction step.
    """
    timestamp: float
    user_input: str
    response: str

    state_snapshot: Dict[str, Any]
    engrams: Dict[str, int]

    axiom_pressure: int
    primitive_saturation: int

    drift_status: str

    previous_hash: str
    hash: str = field(init=False)

    def __post_init__(self):
        self.hash = self.compute_hash()

    def compute_hash(self) -> str:
        """
        Cryptographic hash of the entry for chain integrity.
        """
        entry_data = {
            "timestamp": self.timestamp,
            "user_input": self.user_input,
            "response": self.response,
            "state_snapshot": self.state_snapshot,
            "engrams": self.engrams,
            "axiom_pressure": self.axiom_pressure,
            "primitive_saturation": self.primitive_saturation,
            "drift_status": self.drift_status,
            "previous_hash": self.previous_hash
        }

        encoded = json.dumps(entry_data, sort_keys=True).encode()
        return hashlib.sha256(encoded).hexdigest()