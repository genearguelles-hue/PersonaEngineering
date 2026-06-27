import json
import sys
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker


SCHEMA_PATH = Path("schemas/persona_test_event.schema.json")
EVENT_PATH = Path("tests/sample_persona_test_event.json")


def load_json(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def main() -> int:
    try:
        schema = load_json(SCHEMA_PATH)
        event = load_json(EVENT_PATH)

        validator = Draft202012Validator(
            schema,
            format_checker=FormatChecker()
        )

        errors = sorted(
            validator.iter_errors(event),
            key=lambda error: list(error.path)
        )

        if errors:
            print("❌ persona_test_event validation failed:\n")

            for error in errors:
                path = ".".join(str(part) for part in error.path)
                location = path if path else "<root>"
                print(f"- {location}: {error.message}")

            return 1

        print("✅ persona_test_event is valid.")
        return 0

    except Exception as error:
        print(f"❌ Validation error: {error}")
        return 1


if __name__ == "__main__":
    sys.exit(main())