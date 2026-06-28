import json
from pathlib import Path
from typing import Any, Dict, List


DEFAULT_PERSONAS_DIR = Path("personas")


def load_persona_definition(
    persona_id: str,
    personas_dir: Path = DEFAULT_PERSONAS_DIR
) -> Dict[str, Any]:
    candidate_paths = [
        personas_dir / persona_id / "persona.json",
        personas_dir / f"{persona_id}.json",
    ]

    for path in candidate_paths:
        if path.exists():
            with path.open("r", encoding="utf-8") as file:
                return json.load(file)

    raise FileNotFoundError(
        f"Could not find persona definition for '{persona_id}'. "
        f"Checked: {', '.join(str(path) for path in candidate_paths)}"
    )


def get_persona_body(persona_definition: Dict[str, Any]) -> Dict[str, Any]:
    """
    Supports Persona Foundry exports shaped as:

    {
      "persona": {
        "axioms": [],
        "primitives": [],
        "engramSchema": {}
      }
    }

    Also supports flat persona definitions.
    """
    persona_body = persona_definition.get("persona")

    if isinstance(persona_body, dict):
        return persona_body

    return persona_definition


def extract_axioms(persona_definition: Dict[str, Any]) -> List[Dict[str, str]]:
    persona_body = get_persona_body(persona_definition)

    raw_axioms = (
        persona_body.get("axioms")
        or persona_body.get("persona_axioms")
        or persona_body.get("authority_boundaries")
        or []
    )

    return normalize_parameter_list(raw_axioms, default_prefix="AX")


def extract_primitives(persona_definition: Dict[str, Any]) -> List[Dict[str, str]]:
    persona_body = get_persona_body(persona_definition)

    raw_primitives = (
        persona_body.get("primitives")
        or persona_body.get("persona_primitives")
        or persona_body.get("responsibilities")
        or []
    )

    return normalize_parameter_list(raw_primitives, default_prefix="PR")


def extract_engrams(persona_definition: Dict[str, Any]) -> List[Dict[str, str]]:
    persona_body = get_persona_body(persona_definition)

    raw_engrams = (
        persona_body.get("engrams")
        or persona_body.get("memory")
        or []
    )

    if raw_engrams:
        return normalize_parameter_list(raw_engrams, default_prefix="EN")

    engram_schema = persona_body.get("engramSchema", {})

    if not isinstance(engram_schema, dict):
        return []

    schema_engrams: List[Dict[str, str]] = []

    allowed_memory_types = engram_schema.get("allowedMemoryTypes", [])
    forbidden_memory_types = engram_schema.get("forbiddenMemoryTypes", [])

    for item in allowed_memory_types:
        schema_engrams.append({
            "id": f"allowed_{slugify(str(item))}",
            "description": f"Allowed memory type: {item}"
        })

    for item in forbidden_memory_types:
        schema_engrams.append({
            "id": f"forbidden_{slugify(str(item))}",
            "description": f"Forbidden memory type: {item}"
        })

    return normalize_parameter_list(schema_engrams, default_prefix="EN")


def slugify(value: str) -> str:
    return (
        value.strip()
        .lower()
        .replace(" ", "_")
        .replace("/", "_")
        .replace("-", "_")
    )


def parameter_key(default_prefix: str) -> str:
    if default_prefix == "AX":
        return "axiom_id"

    if default_prefix == "PR":
        return "primitive_id"

    return "engram_id"


def normalize_parameter_list(
    values: Any,
    default_prefix: str
) -> List[Dict[str, str]]:
    normalized: List[Dict[str, str]] = []
    id_key = parameter_key(default_prefix)

    if isinstance(values, dict):
        values = [values]

    if not isinstance(values, list):
        return normalized

    for index, value in enumerate(values, start=1):
        parameter_id = f"{default_prefix}-{index:03d}"

        if isinstance(value, str):
            normalized.append({
                id_key: parameter_id,
                "description": value
            })

        elif isinstance(value, dict):
            title = (
                value.get("title")
                or value.get("name")
                or value.get("rule")
                or value.get("text")
            )

            description = (
                value.get("description")
                or title
                or json.dumps(value, ensure_ascii=False)
            )

            if default_prefix == "PR":
                primitive_name = value.get("name")
                primitive_value = value.get("value")
                primitive_description = value.get("description")

                if primitive_name and primitive_value and primitive_description:
                    description = (
                        f"{primitive_name}: {primitive_value} — "
                        f"{primitive_description}"
                    )

            existing_id = (
                value.get("axiom_id")
                or value.get("primitive_id")
                or value.get("engram_id")
                or value.get("id")
                or parameter_id
            )

            normalized.append({
                id_key: str(existing_id),
                "description": str(description)
            })

    return normalized


def enrich_event_with_persona_parameters(
    event: Dict[str, Any],
    personas_dir: Path = DEFAULT_PERSONAS_DIR
) -> Dict[str, Any]:
    persona_id = event.get("persona", {}).get("persona_id")

    if not persona_id:
        raise ValueError("Event is missing persona.persona_id")

    persona_definition = load_persona_definition(persona_id, personas_dir)

    event.setdefault("persona_parameters", {})
    event["persona_parameters"]["active_axioms"] = extract_axioms(persona_definition)
    event["persona_parameters"]["active_primitives"] = extract_primitives(persona_definition)
    event["persona_parameters"]["active_engrams"] = extract_engrams(persona_definition)

    return event