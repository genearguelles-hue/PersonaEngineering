import json
from pathlib import Path
from typing import Any, Dict, Optional

from persona_test_harness.event_validator import validate_persona_test_event


DEFAULT_LEDGER_PATH = Path("persona_ledger/persona_test_events.jsonl")


def write_persona_test_event(
    event: Dict[str, Any],
    ledger_path: Path = DEFAULT_LEDGER_PATH,
    validate: bool = True
) -> Optional[str]:
    if validate:
        errors = validate_persona_test_event(event)
        if errors:
            return "\n".join(errors)

    ledger_path.parent.mkdir(parents=True, exist_ok=True)

    with ledger_path.open("a", encoding="utf-8") as file:
        file.write(json.dumps(event, ensure_ascii=False) + "\n")

    return None