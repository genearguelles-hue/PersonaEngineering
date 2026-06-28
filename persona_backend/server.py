#!/usr/bin/env python3

"""
Persona Backend Prototype

Local backend proxy for PersonaFoundry iOS.

Flow:
PersonaFoundry iOS
→ local FastAPI backend
→ OpenAI API
→ generated persona-governed post
→ response back to iOS app

Run:
    source .venv/bin/activate
    uvicorn server:app --host 0.0.0.0 --port 8000 --reload
"""

from __future__ import annotations
from pathlib import Path
from datetime import datetime, timezone
from uuid import uuid4
import json
import os
from datetime import datetime, timezone
from typing import Any, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from openai import OpenAI
from pydantic import BaseModel, Field


load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not OPENAI_API_KEY:
    raise RuntimeError(
        "OPENAI_API_KEY is missing. Add it to your .env file before starting the server."
    )

client = OpenAI(api_key=OPENAI_API_KEY)

app = FastAPI(
    title="Persona Backend Prototype",
    version="0.1.0",
    description="Local backend proxy for PersonaFoundry persona-governed generation.",
)


class PersonaAxiom(BaseModel):
    id: Optional[str] = None
    title: str
    description: str
    isRequired: bool = True


class PersonaPrimitive(BaseModel):
    id: Optional[str] = None
    name: str
    value: str
    description: str


class EngramSchema(BaseModel):
    allowedMemoryTypes: list[str] = Field(default_factory=list)
    forbiddenMemoryTypes: list[str] = Field(default_factory=list)


class PersonaSpec(BaseModel):
    id: str
    name: str
    missionType: str
    missionDescription: str
    coreIdentity: str
    axioms: list[PersonaAxiom]
    primitives: list[PersonaPrimitive]
    engramSchema: EngramSchema
    avatarPrompt: Optional[str] = ""
    systemPrompt: str


class GeneratePostRequest(BaseModel):
    persona: PersonaSpec
    userIntent: str
    postStyle: Optional[str] = "clear, concise, reflective"
    platform: Optional[str] = "general"
    maxWords: Optional[int] = 250

class GeneratePostFromPersonaRequest(BaseModel):
    persona_id: str
    userIntent: str
    postStyle: Optional[str] = "clear, concise, reflective"
    platform: Optional[str] = "general"
    maxWords: Optional[int] = 250

class GeneratePostResponse(BaseModel):
    status: str
    model: str
    generatedAt: str
    personaName: str
    output: str
    validationNotes: list[str]

def normalize_persona_data(raw_data: dict, persona_id: str) -> dict:
    # PersonaFoundry exports wrap the actual persona inside "persona".
    if isinstance(raw_data, dict) and "persona" in raw_data and isinstance(raw_data["persona"], dict):
        data = raw_data["persona"]
    else:
        data = raw_data

    required_runtime_keys = {
        "id",
        "name",
        "missionType",
        "missionDescription",
        "coreIdentity",
        "axioms",
        "primitives",
        "engramSchema",
        "systemPrompt",
    }

    # If already in runtime format, return it unchanged.
    if required_runtime_keys.issubset(set(data.keys())):
        return data

    name = data.get("name") or data.get("title") or persona_id

    mission_description = (
        data.get("missionDescription")
        or data.get("mission")
        or data.get("description")
        or f"Operational persona loaded from legacy persona file: {persona_id}."
    )

    core_identity = (
        data.get("coreIdentity")
        or data.get("identity")
        or data.get("role")
        or name
    )

    normalized_axioms = []
    for i, axiom in enumerate(data.get("axioms", []), start=1):
        title = (
            axiom.get("title")
            or axiom.get("name")
            or axiom.get("statement")
            or f"Axiom {i}"
        )

        description = (
            axiom.get("description")
            or axiom.get("statement")
            or title
        )

        normalized_axioms.append({
            "id": axiom.get("id") or f"A{i}",
            "title": title,
            "description": description,
            "isRequired": axiom.get("isRequired", True)
        })

    normalized_primitives = []
    for i, primitive in enumerate(data.get("primitives", []), start=1):
        name_value = (
            primitive.get("name")
            or primitive.get("title")
            or f"Primitive {i}"
        )

        description = (
            primitive.get("description")
            or primitive.get("statement")
            or name_value
        )

        normalized_primitives.append({
            "id": primitive.get("id") or f"P{i}",
            "name": name_value,
            "value": primitive.get("value") or name_value,
            "description": description
        })

    engram_schema = data.get("engramSchema") or {
        "allowedMemoryTypes": [],
        "forbiddenMemoryTypes": []
    }

    system_prompt = data.get("systemPrompt") or (
        f"You are operating as {name}. "
        f"Mission: {mission_description} "
        f"Core identity: {core_identity} "
        "Maintain persona coherence, respect all axioms, and follow the defined primitives."
    )

    return {
        "id": data.get("id") or persona_id,
        "name": name,
        "missionType": data.get("missionType") or data.get("type") or "legacy_persona",
        "missionDescription": mission_description,
        "coreIdentity": core_identity,
        "axioms": normalized_axioms,
        "primitives": normalized_primitives,
        "engramSchema": engram_schema,
        "avatarPrompt": data.get("avatarPrompt", ""),
        "systemPrompt": system_prompt
    }

def load_persona_by_id(persona_id: str) -> PersonaSpec:
    persona_path = Path("personas") / persona_id / "persona.json"

    if not persona_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Persona '{persona_id}' not found."
        )

    try:
        with persona_path.open("r", encoding="utf-8") as f:
            raw_data = json.load(f)

        persona_data = normalize_persona_data(raw_data, persona_id)

        return PersonaSpec(**persona_data)

    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Failed to load persona '{persona_id}': {str(e)}"
        )

LEDGER_DIR = Path("persona_ledger")
LEDGER_FILE = LEDGER_DIR / "ledger.jsonl"


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_ledger_entry(entry: dict) -> dict:
    LEDGER_DIR.mkdir(parents=True, exist_ok=True)

    if "ledger_id" not in entry:
        entry["ledger_id"] = str(uuid4())

    if "timestamp" not in entry:
        entry["timestamp"] = now_utc_iso()

    with LEDGER_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    return entry


def read_recent_ledger_entries(limit: int = 10) -> list[dict]:
    if not LEDGER_FILE.exists():
        return []

    entries = []

    with LEDGER_FILE.open("r", encoding="utf-8") as f:
        lines = f.readlines()

    for line in lines[-limit:]:
        line = line.strip()
        if not line:
            continue

        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            entries.append({
                "event_type": "ledger_parse_error",
                "raw_line": line
            })

    return entries

@app.get("/health")
def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "service": "Persona Backend Prototype",
        "time": datetime.now(timezone.utc).isoformat(),
    }

@app.get("/personas")
def list_personas():
    personas_dir = Path("personas")
    personas = []
    if not personas_dir.exists():
        return {
            "count": 0,
            "personas": []
        }

    for persona_file in personas_dir.glob("*/persona.json"):
        try:
            with persona_file.open("r", encoding="utf-8") as f:
                data = json.load(f)
            persona_id = (
                data.get("persona_id")
                or data.get("id")
                or persona_file.parent.name
            )
            name = (
                data.get("name")
                or data.get("display_name")
                or persona_file.parent.name
            )
            personas.append({
                "persona_id": persona_id,
                "name": name,
                "path": str(persona_file),
                "status": data.get("status", "active")
            })
        except Exception as e:
            personas.append({
                "persona_id": persona_file.parent.name,
                "path": str(persona_file),
                "status": "error",
                "error": str(e)
            })
    return {
        "count": len(personas),
        "personas": personas
    }

@app.get("/personas/{persona_id}")
def get_persona_detail(persona_id: str):
    persona_path = Path("personas") / persona_id / "persona.json"

    if not persona_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Persona '{persona_id}' not found."
        )

    try:
        with persona_path.open("r", encoding="utf-8") as f:
            raw_data = json.load(f)

        persona_data = normalize_persona_data(raw_data, persona_id)

        return {
            "persona_id": persona_data.get("id", persona_id),
            "name": persona_data.get("name", persona_id),
            "missionType": persona_data.get("missionType"),
            "missionDescription": persona_data.get("missionDescription"),
            "coreIdentity": persona_data.get("coreIdentity"),
            "axioms": persona_data.get("axioms", []),
            "primitives": persona_data.get("primitives", []),
            "engramSchema": persona_data.get("engramSchema", {}),
            "avatarPrompt": persona_data.get("avatarPrompt", ""),
            "systemPrompt": persona_data.get("systemPrompt", "")
        }

    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Failed to retrieve persona '{persona_id}': {str(e)}"
        )

@app.get("/ledger")
def get_ledger(limit: int = 10):
    if limit < 1:
        limit = 1

    if limit > 100:
        limit = 100

    entries = read_recent_ledger_entries(limit)

    return {
        "count": len(entries),
        "entries": entries
    }

@app.post("/generate-post", response_model=GeneratePostResponse)
def generate_post(request: GeneratePostRequest) -> GeneratePostResponse:
    if not request.userIntent.strip():
        raise HTTPException(status_code=400, detail="userIntent must not be empty.")

    if not request.persona.axioms:
        raise HTTPException(status_code=400, detail="persona must include at least one axiom.")

    if not request.persona.primitives:
        raise HTTPException(status_code=400, detail="persona must include at least one primitive.")

    compiled_prompt = compile_persona_runtime_prompt(request)

    try:
        response = client.responses.create(
            model="gpt-4.1-mini",
            input=compiled_prompt,
        )
    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"OpenAI request failed: {error}",
        ) from error

    output_text = extract_output_text(response)

    return GeneratePostResponse(
        status="success",
        model="gpt-4.1-mini",
        generatedAt=datetime.now(timezone.utc).isoformat(),
        personaName=request.persona.name,
        output=output_text,
        validationNotes=basic_validation_notes(
            persona=request.persona,
            output=output_text,
        ),
    )

@app.post("/generate-post-from-persona", response_model=GeneratePostResponse)
def generate_post_from_persona(request: GeneratePostFromPersonaRequest):
    persona = load_persona_by_id(request.persona_id)

    generate_request = GeneratePostRequest(
        persona=persona,
        userIntent=request.userIntent,
        postStyle=request.postStyle,
        platform=request.platform,
        maxWords=request.maxWords
    )

    response = generate_post(generate_request)

    write_ledger_entry({
        "event_type": "interaction_event",
        "operation": "generate_post_from_persona",
        "persona_id": request.persona_id,
        "persona_name": response.personaName,
        "model": response.model,
        "status": response.status,
        "userIntent": request.userIntent,
        "postStyle": request.postStyle,
        "platform": request.platform,
        "maxWords": request.maxWords,
        "output_preview": response.output[:500],
        "output_length_chars": len(response.output),
        "validationNotes": response.validationNotes
    })

    return response

    return generate_post(generate_request)

def compile_persona_runtime_prompt(request: GeneratePostRequest) -> str:
    persona = request.persona

    axioms_text = "\n".join(
        f"- {axiom.title}: {axiom.description}"
        for axiom in persona.axioms
    )

    primitives_text = "\n".join(
        f"- {primitive.name}: {primitive.value} — {primitive.description}"
        for primitive in persona.primitives
    )

    allowed_engrams = "\n".join(
        f"- {item}"
        for item in persona.engramSchema.allowedMemoryTypes
    ) or "- None specified"

    forbidden_engrams = "\n".join(
        f"- {item}"
        for item in persona.engramSchema.forbiddenMemoryTypes
    ) or "- None specified"

    return f"""
You are operating as a persona-governed generation agent.

You must generate a user-facing post using the Persona Engineering specification below.

PERSONA NAME:
{persona.name}

MISSION TYPE:
{persona.missionType}

MISSION:
{persona.missionDescription}

CORE IDENTITY:
{persona.coreIdentity}

PERSONA AXIOMS:
{axioms_text}

PERSONA PRIMITIVES:
{primitives_text}

ENGRAM POLICY:
You may use or adapt around:
{allowed_engrams}

You must not use, infer, or exploit:
{forbidden_engrams}

BASE SYSTEM PROMPT:
{persona.systemPrompt}

USER INTENT:
{request.userIntent}

TARGET PLATFORM:
{request.platform}

POST STYLE:
{request.postStyle}

MAX WORDS:
{request.maxWords}

OUTPUT REQUIREMENTS:
- Write only the final post.
- Do not explain the persona specification.
- Do not mention axioms, primitives, or engrams unless the user explicitly asked for that.
- Preserve user autonomy.
- Avoid manipulation, coercion, dependency-forming language, or false certainty.
- Maintain the persona's mission, boundaries, and interactional identity.
- Keep the output under the requested word limit.
""".strip()


def extract_output_text(response: Any) -> str:
    """
    The OpenAI Python SDK usually exposes response.output_text for Responses API calls.
    This fallback keeps the prototype resilient if the shape differs.
    """

    output_text = getattr(response, "output_text", None)

    if isinstance(output_text, str) and output_text.strip():
        return output_text.strip()

    try:
        chunks: list[str] = []
        for item in response.output:
            if getattr(item, "type", None) == "message":
                for content in item.content:
                    text = getattr(content, "text", None)
                    if text:
                        chunks.append(text)
        if chunks:
            return "\n".join(chunks).strip()
    except Exception:
        pass

    return str(response)


def basic_validation_notes(persona: PersonaSpec, output: str) -> list[str]:
    """
    Lightweight local validation for the prototype.

    This is not a full axiom verifier yet. It gives basic diagnostics
    that we can later replace with a true Persona Engineering validation layer.
    """

    notes: list[str] = []

    if output.strip():
        notes.append("Generated output is non-empty.")
    else:
        notes.append("Warning: generated output is empty.")

    required_axioms = [axiom.title for axiom in persona.axioms if axiom.isRequired]

    if required_axioms:
        notes.append(
            "Required axioms supplied: " + ", ".join(required_axioms)
        )

    forbidden_terms = [
        "you must",
        "you have no choice",
        "trust me completely",
        "depend on me",
    ]

    lowered = output.lower()

    detected_terms = [
        term for term in forbidden_terms
        if term in lowered
    ]

    if detected_terms:
        notes.append(
            "Potential autonomy/dependency concern detected: "
            + ", ".join(detected_terms)
        )
    else:
        notes.append("No obvious autonomy/dependency warning terms detected.")

    return notes

@app.post("/ledger/test")
def write_test_ledger_entry():
    entry = write_ledger_entry({
        "event_type": "test_event",
        "source": "manual_test",
        "message": "Ledger write test succeeded."
    })

    return {
        "status": "success",
        "entry": entry
    }
