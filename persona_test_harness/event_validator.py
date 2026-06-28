import json
from pathlib import Path
from typing import Any, Dict, List

from jsonschema import Draft202012Validator, FormatChecker


DEFAULT_SCHEMA_PATH = Path("schemas/persona_test_event.schema.json")


def load_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def validate_persona_test_event(
    event: Dict[str, Any],
    schema_path: Path = DEFAULT_SCHEMA_PATH
) -> List[str]:
    schema = load_json(schema_path)

    validator = Draft202012Validator(
        schema,
        format_checker=FormatChecker()
    )

    errors = sorted(
        validator.iter_errors(event),
        key=lambda error: list(error.path)
    )

    messages = []

    for error in errors:
        path = ".".join(str(part) for part in error.path)
        location = path if path else "<root>"
        messages.append(f"{location}: {error.message}")

    return messages