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


class GeneratePostResponse(BaseModel):
    status: str
    model: str
    generatedAt: str
    personaName: str
    output: str
    validationNotes: list[str]


@app.get("/health")
def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "service": "Persona Backend Prototype",
        "time": datetime.now(timezone.utc).isoformat(),
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
