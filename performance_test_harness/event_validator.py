"""Validation helpers for performance-run Ledger events."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SCHEMA_PATH = PROJECT_ROOT / "schemas" / "performance_run_event.schema.json"
SCHEMA_PATHS = {
    "pe.performance.run.event.v1": DEFAULT_SCHEMA_PATH,
    "pe.performance.run.event.v2": (
        PROJECT_ROOT / "schemas" / "performance_run_event_v2.schema.json"
    ),
}


def validate_performance_run_event(
    event: dict[str, Any], schema_path: Path | None = None
) -> list[str]:
    if schema_path is None:
        version = event.get("schema_version")
        schema_path = SCHEMA_PATHS.get(version)
        if schema_path is None:
            return [f"schema_version: unsupported performance event schema: {version!r}"]
    with schema_path.open("r", encoding="utf-8") as handle:
        schema = json.load(handle)

    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(event), key=lambda item: list(item.path))
    messages: list[str] = []
    for error in errors:
        path = ".".join(str(part) for part in error.path)
        messages.append(f"{path or '<root>'}: {error.message}")
    return messages
