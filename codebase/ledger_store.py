import json
from typing import Any, Dict, List

from ledger import Ledger
from ledger_entry import LedgerEntry


class LedgerStore:
    """
    Save and load Ledger objects as JSON.
    """

    @staticmethod
    def save(ledger: Ledger, filepath: str) -> None:
        records: List[Dict[str, Any]] = []

        for entry in ledger.entries():
            records.append({
                "timestamp": entry.timestamp,
                "user_input": entry.user_input,
                "response": entry.response,
                "state_snapshot": entry.state_snapshot,
                "engrams": entry.engrams,
                "axiom_pressure": entry.axiom_pressure,
                "primitive_saturation": entry.primitive_saturation,
                "drift_status": entry.drift_status,
                "previous_hash": entry.previous_hash,
                "hash": entry.hash,
            })

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(records, f, indent=2)

    @staticmethod
    def load(filepath: str) -> Ledger:
        with open(filepath, "r", encoding="utf-8") as f:
            records = json.load(f)

        ledger = Ledger()

        for record in records:
            entry = LedgerEntry(
                timestamp=record["timestamp"],
                user_input=record["user_input"],
                response=record["response"],
                state_snapshot=record["state_snapshot"],
                engrams=record["engrams"],
                axiom_pressure=record["axiom_pressure"],
                primitive_saturation=record["primitive_saturation"],
                drift_status=record["drift_status"],
                previous_hash=record["previous_hash"],
            )

            if entry.hash != record["hash"]:
                raise ValueError("Ledger file integrity failure: entry hash mismatch.")

            ledger.append(entry)

        return ledger