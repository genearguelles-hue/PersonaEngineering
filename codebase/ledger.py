from typing import List, Optional

from ledger_entry import LedgerEntry


class Ledger:
    """
    Minimal append-only ledger for persona interaction records.

    Responsibilities:
    - maintain ordered ledger entries
    - provide previous hash for new entries
    - append new entries
    - verify hash-chain integrity
    - expose ledger history
    """

    def __init__(self) -> None:
        self._entries: List[LedgerEntry] = []

    def __len__(self) -> int:
        return len(self._entries)

    def is_empty(self) -> bool:
        return len(self._entries) == 0

    def entries(self) -> List[LedgerEntry]:
        """
        Return a shallow copy of the ledger history.
        """
        return list(self._entries)

    def last_entry(self) -> Optional[LedgerEntry]:
        """
        Return the most recent ledger entry, if any.
        """
        if self.is_empty():
            return None
        return self._entries[-1]

    def last_hash(self) -> str:
        """
        Return the hash of the most recent entry,
        or the genesis marker if the ledger is empty.
        """
        last = self.last_entry()
        return last.hash if last is not None else "GENESIS"

    def append(self, entry: LedgerEntry) -> None:
        """
        Append a new entry to the ledger.

        Enforces correct chain linkage by requiring the
        entry's previous_hash to match the current last_hash.
        """
        expected_previous_hash = self.last_hash()

        if entry.previous_hash != expected_previous_hash:
            raise ValueError(
                "Ledger append rejected: previous_hash does not match "
                f"the current ledger tail. Expected {expected_previous_hash}, "
                f"got {entry.previous_hash}."
            )

        self._entries.append(entry)

    def verify(self) -> bool:
        """
        Verify full ledger integrity.

        Checks:
        - first entry links to GENESIS
        - each entry hash is internally correct
        - each entry links correctly to the prior entry
        """
        previous_hash = "GENESIS"

        for entry in self._entries:
            if entry.previous_hash != previous_hash:
                return False

            if entry.hash != entry.compute_hash():
                return False

            previous_hash = entry.hash

        return True