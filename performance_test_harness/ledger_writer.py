"""Append-only, hash-chained writer for performance-run Ledger events."""

from __future__ import annotations

import hashlib
import json
import os
import threading
from contextlib import contextmanager
from copy import deepcopy
from pathlib import Path
from typing import Any, Iterator

from performance_test_harness.event_validator import validate_performance_run_event


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LEDGER_PATH = PROJECT_ROOT / "persona_ledger" / "performance_run_events.jsonl"
_WRITE_LOCK = threading.RLock()


class LedgerWriteError(RuntimeError):
    """The event could not be safely appended to the performance Ledger."""


@contextmanager
def _process_lock(ledger_path: Path) -> Iterator[None]:
    """Serialize writers across processes on the supported macOS/Linux hosts."""

    lock_path = ledger_path.with_name(ledger_path.name + ".lock")
    with lock_path.open("a+", encoding="utf-8") as lock_handle:
        try:
            import fcntl
        except ImportError:  # pragma: no cover - Windows fallback
            yield
            return
        fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock_handle.fileno(), fcntl.LOCK_UN)


def _canonical_json(value: dict[str, Any]) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def _last_event_hash(ledger_path: Path) -> str | None:
    if not ledger_path.exists():
        return None
    last_line = ""
    with ledger_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                last_line = line
    if not last_line:
        return None
    try:
        event = json.loads(last_line)
        digest = event["ledger"]["event_hash"]
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        raise LedgerWriteError("The existing Ledger has an invalid final event") from exc
    if not isinstance(digest, str) or len(digest) != 64:
        raise LedgerWriteError("The existing Ledger has an invalid final event hash")
    return digest


def append_performance_run_event(
    event: dict[str, Any], ledger_path: Path = DEFAULT_LEDGER_PATH
) -> dict[str, Any]:
    """Validate, hash-chain, append, flush, and return the persisted event."""

    ledger_path = Path(ledger_path)
    with _WRITE_LOCK:
        ledger_path.parent.mkdir(parents=True, exist_ok=True)
        with _process_lock(ledger_path):
            previous_hash = _last_event_hash(ledger_path)
            persisted = deepcopy(event)
            persisted["ledger"] = {"previous_event_hash": previous_hash}
            persisted["ledger"]["event_hash"] = hashlib.sha256(
                _canonical_json(persisted)
            ).hexdigest()

            errors = validate_performance_run_event(persisted)
            if errors:
                raise LedgerWriteError("\n".join(errors))

            with ledger_path.open("a", encoding="utf-8") as handle:
                handle.write(
                    json.dumps(persisted, ensure_ascii=False, sort_keys=True) + "\n"
                )
                handle.flush()
                os.fsync(handle.fileno())
            return persisted


def verify_performance_run_ledger(ledger_path: Path = DEFAULT_LEDGER_PATH) -> list[str]:
    """Return validation/hash-chain errors; an empty list means verification passed."""

    ledger_path = Path(ledger_path)
    if not ledger_path.exists():
        return [f"Ledger file not found: {ledger_path}"]

    errors: list[str] = []
    expected_previous: str | None = None
    with ledger_path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError as exc:
                errors.append(f"line {line_number}: invalid JSON: {exc.msg}")
                continue
            for message in validate_performance_run_event(event):
                errors.append(f"line {line_number}: {message}")
            ledger = event.get("ledger", {})
            if ledger.get("previous_event_hash") != expected_previous:
                errors.append(f"line {line_number}: previous_event_hash does not match")
            claimed = ledger.get("event_hash")
            candidate = deepcopy(event)
            candidate.get("ledger", {}).pop("event_hash", None)
            actual = hashlib.sha256(_canonical_json(candidate)).hexdigest()
            if claimed != actual:
                errors.append(f"line {line_number}: event_hash does not match")
            expected_previous = claimed if isinstance(claimed, str) else None
    return errors
