from __future__ import annotations

import hashlib
import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _canonical_json(value: dict[str, Any]) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


class MissionLedger:
    """Per-mission ordered hash chain and evidence manifest."""

    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.missions_dir = data_dir / "missions"
        self.missions_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def mission_dir(self, mission_id: str) -> Path:
        path = self.missions_dir / mission_id
        path.mkdir(parents=True, exist_ok=True)
        return path

    def append(
        self,
        mission_id: str,
        event_type: str,
        state: str,
        details: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        ledger_path = self.mission_dir(mission_id) / "events.jsonl"
        with self._lock:
            existing = self.events(mission_id)
            previous_hash = existing[-1]["event_hash"] if existing else "GENESIS"
            event = {
                "schema_version": "pe.mission-event.v1",
                "mission_id": mission_id,
                "sequence": len(existing) + 1,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "event_type": event_type,
                "state": state,
                "details": details or {},
                "previous_hash": previous_hash,
            }
            event["event_hash"] = hashlib.sha256(
                _canonical_json(event).encode("utf-8")
            ).hexdigest()
            with ledger_path.open("a", encoding="utf-8") as handle:
                handle.write(_canonical_json(event) + "\n")
            return event

    def events(self, mission_id: str) -> list[dict[str, Any]]:
        ledger_path = self.missions_dir / mission_id / "events.jsonl"
        if not ledger_path.exists():
            return []
        events: list[dict[str, Any]] = []
        for line in ledger_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                events.append(json.loads(line))
        return events

    def verify(self, mission_id: str) -> dict[str, Any]:
        events = self.events(mission_id)
        previous_hash = "GENESIS"
        for index, event in enumerate(events):
            stored_hash = event.get("event_hash")
            unsigned = {key: value for key, value in event.items() if key != "event_hash"}
            expected = hashlib.sha256(
                _canonical_json(unsigned).encode("utf-8")
            ).hexdigest()
            if event.get("previous_hash") != previous_hash or stored_hash != expected:
                return {
                    "valid": False,
                    "event_count": len(events),
                    "failure_sequence": index + 1,
                }
            previous_hash = stored_hash
        return {
            "valid": True,
            "event_count": len(events),
            "terminal_hash": previous_hash,
        }

    def seal_manifest(self, mission_id: str) -> dict[str, Any]:
        mission_dir = self.mission_dir(mission_id)
        manifest_path = mission_dir / "evidence-manifest.json"
        artifacts = []
        for path in sorted(mission_dir.rglob("*")):
            if not path.is_file() or path == manifest_path:
                continue
            artifacts.append(
                {
                    "path": str(path.relative_to(mission_dir)),
                    "size_bytes": path.stat().st_size,
                    "sha256": _file_hash(path),
                }
            )
        verification = self.verify(mission_id)
        manifest = {
            "schema_version": "pe.mission-evidence-manifest.v1",
            "mission_id": mission_id,
            "sealed_at": datetime.now(timezone.utc).isoformat(),
            "ledger": verification,
            "artifacts": artifacts,
        }
        manifest["manifest_hash"] = hashlib.sha256(
            _canonical_json(manifest).encode("utf-8")
        ).hexdigest()
        manifest_path.write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return manifest

    def manifest(self, mission_id: str) -> dict[str, Any] | None:
        path = self.missions_dir / mission_id / "evidence-manifest.json"
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None
