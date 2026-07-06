import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4

from fastapi import Depends, FastAPI, HTTPException
from fastapi.security import APIKeyHeader
from dotenv import load_dotenv
from pydantic import BaseModel, Field


REPO_ROOT = Path(__file__).resolve().parent.parent
PERSONAS_DIR = REPO_ROOT / "personas"
INDEX_FILE = PERSONAS_DIR / "index.json"
LEDGER_DIR = Path(__file__).resolve().parent / "ledger"
LEDGER_FILE = LEDGER_DIR / "process_ledger.jsonl"

load_dotenv()

PERSONA_API_KEY = os.getenv("PERSONA_API_KEY")
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

app = FastAPI(
    title="Persona Engineering Domain API",
    version="1.0.0",
    description="API for reading machine-readable persona specifications from the Persona Engineering domain.",
    servers=[
        {
            "url": "https://backed-berry-wives-finishing.trycloudflare.com",
            "description": "Cloudflared public tunnel for local Persona Engineering API"
        }
    ],
)


class InstantiateRequest(BaseModel):
    persona_id: str = Field(..., description="Stable ID of the persona to instantiate.")
    mission_context: Optional[str] = Field(
        default=None,
        description="Optional user or task context for the requested instantiation.",
    )
    user_request: Optional[str] = Field(
        default=None,
        description="Optional original user request.",
    )


class InstantiateResponse(BaseModel):
    persona_id: str
    name: str
    version: str
    status: str
    runtime_summary: str
    system_instruction_fragment: str
    opening_behavior: Optional[str] = None
    axioms: List[Dict[str, Any]]
    primitives: List[Dict[str, Any]]
    engram_schema: List[Dict[str, Any]]
    mission_context: Optional[str] = None
    user_request: Optional[str] = None

class ProcessRequest(BaseModel):
    persona_id: str = Field(..., description="Stable ID of the persona to use for processing.")
    user_post: str = Field(..., description="The user post or message to route through the Persona Engineering process chain.")
    mission_context: Optional[str] = Field(
        default=None,
        description="Optional mission or task context for the process chain.",
    )
    requested_operation: Optional[str] = Field(
        default="respond",
        description="The intended operation, such as respond, review, assess, coach, or draft.",
    )


class ValidationFinding(BaseModel):
    severity: str
    category: str
    message: str


class ProcessResponse(BaseModel):
    ledger_id: str
    timestamp: str
    persona_id: str
    persona_name: str
    requested_operation: str
    validation_status: str
    validation_findings: List[ValidationFinding]
    axiom_risk_findings: List[ValidationFinding]
    drift_risk_findings: List[ValidationFinding]
    response_envelope: Dict[str, Any]
    runtime_instruction_fragment: str
    ledger_recorded: bool

class LedgerEntry(BaseModel):
    ledger_id: Optional[str] = None
    timestamp: Optional[str] = None
    persona_id: Optional[str] = None
    persona_name: Optional[str] = None
    requested_operation: Optional[str] = None
    mission_context: Optional[str] = None
    user_post: Optional[str] = None
    validation_findings: Optional[List[Dict[str, Any]]] = None
    axiom_risk_findings: Optional[List[Dict[str, Any]]] = None
    drift_risk_findings: Optional[List[Dict[str, Any]]] = None
    response_envelope: Optional[Dict[str, Any]] = None


class LedgerResponse(BaseModel):
    count: int
    entries: List[Dict[str, Any]]

class ValidateSpecRequest(BaseModel):
    persona_id: Optional[str] = Field(
        default=None,
        description="Stable ID of an existing persona to validate."
    )
    spec: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Optional raw persona specification object to validate."
    )


class ValidateSpecResponse(BaseModel):
    valid: bool
    persona_id: Optional[str] = None
    error_count: int
    errors: List[str]

def read_json_file(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"File not found: {path.name}")

    try:
        import json

        with path.open("r", encoding="utf-8") as file:
            return json.load(file)
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to read JSON file {path.name}: {exc}",
        )


def load_index() -> Dict[str, Any]:
    if not INDEX_FILE.exists():
        raise HTTPException(
            status_code=500,
            detail="Persona index file not found. Expected personas/index.json.",
        )

    return read_json_file(INDEX_FILE)


def get_persona_entry(persona_id: str) -> Dict[str, Any]:
    index = load_index()
    personas = index.get("personas", [])

    for persona in personas:
        if persona.get("id") == persona_id:
            return persona

    raise HTTPException(
        status_code=404,
        detail=f"Persona not found: {persona_id}",
    )


def load_persona(persona_id: str) -> Dict[str, Any]:
    entry = get_persona_entry(persona_id)
    filename = entry.get("file")

    if not filename:
        raise HTTPException(
            status_code=500,
            detail=f"Persona registry entry missing file field: {persona_id}",
        )

    persona_path = PERSONAS_DIR / filename
    return read_json_file(persona_path)

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalize_text(text: Optional[str]) -> str:
    return (text or "").strip().lower()


def contains_any(text: str, terms: List[str]) -> bool:
    lowered = normalize_text(text)
    return any(term in lowered for term in terms)


def validate_interaction_boundaries(persona: Dict[str, Any], user_post: str) -> List[Dict[str, str]]:
    """
    Lightweight deterministic validation against declared interaction boundaries.

    This does not replace formal verification. It flags obvious boundary risks
    so the Custom GPT can respond within the persona's allowed envelope.
    """
    findings: List[Dict[str, str]] = []
    boundaries = persona.get("interaction_boundaries", {})
    disallowed = boundaries.get("disallowed", [])
    handoff_triggers = boundaries.get("handoff_triggers", [])

    post = normalize_text(user_post)

    risk_terms = {
        "diagnose mental health conditions": ["diagnose me", "mental disorder", "clinical diagnosis"],
        "declare legal, medical, or regulatory compliance certification": ["certify", "legally compliant", "regulatory approval"],
        "coerce motivation": ["force me", "make me do it", "shame me into"],
        "create dependency": ["i cannot do this without you", "only you can help me", "i need you forever"],
        "override user agency": ["decide for me", "make the decision for me"],
        "use shame or fear as leverage": ["shame me", "scare me into", "make me afraid"],
    }

    for boundary in disallowed:
        terms = risk_terms.get(normalize_text(boundary), [])
        if terms and contains_any(post, terms):
            findings.append(
                {
                    "severity": "high",
                    "category": "interaction_boundary",
                    "message": f"User post may implicate disallowed boundary: {boundary}",
                }
            )

    handoff_terms = {
        "user expresses intent to self-harm": ["kill myself", "self-harm", "hurt myself", "end my life"],
        "user requests clinical diagnosis": ["diagnose me", "do i have depression", "do i have adhd"],
        "user appears to need professional medical, legal, or financial support": ["lawsuit", "medical emergency", "investment advice"],
        "assessment involves regulated professional advice": ["legal advice", "medical advice", "financial advice"],
        "user requests certification rather than diagnostic assessment": ["certify this", "officially approve"],
        "evidence is insufficient for the requested conclusion": ["prove without evidence", "guarantee this is true"],
    }

    for trigger in handoff_triggers:
        terms = handoff_terms.get(normalize_text(trigger), [])
        if terms and contains_any(post, terms):
            findings.append(
                {
                    "severity": "high",
                    "category": "handoff_trigger",
                    "message": f"User post may trigger handoff condition: {trigger}",
                }
            )

    if not findings:
        findings.append(
            {
                "severity": "info",
                "category": "interaction_boundary",
                "message": "No obvious interaction-boundary violation detected by deterministic checks.",
            }
        )

    return findings


def check_axiom_risk(persona: Dict[str, Any], user_post: str) -> List[Dict[str, str]]:
    """
    Lightweight axiom-risk screening.
    """
    findings: List[Dict[str, str]] = []
    post = normalize_text(user_post)
    axioms = persona.get("axioms", [])

    for axiom in axioms:
        statement = normalize_text(axiom.get("statement"))

        if "autonomy" in statement and contains_any(post, ["decide for me", "make the decision", "take control"]):
            findings.append(
                {
                    "severity": "medium",
                    "category": "axiom_risk",
                    "message": f"Possible autonomy risk related to axiom: {axiom.get('statement')}",
                }
            )

        if "dependency" in statement and contains_any(post, ["only you can help", "i need you", "without you i cannot"]):
            findings.append(
                {
                    "severity": "medium",
                    "category": "axiom_risk",
                    "message": f"Possible dependency risk related to axiom: {axiom.get('statement')}",
                }
            )

        if "uncertainty" in statement and contains_any(post, ["guarantee", "prove absolutely", "be certain"]):
            findings.append(
                {
                    "severity": "medium",
                    "category": "axiom_risk",
                    "message": f"Possible uncertainty-transparency risk related to axiom: {axiom.get('statement')}",
                }
            )

        if "coercive" in statement and contains_any(post, ["shame me", "force me", "manipulate me"]):
            findings.append(
                {
                    "severity": "high",
                    "category": "axiom_risk",
                    "message": f"Possible coercion risk related to axiom: {axiom.get('statement')}",
                }
            )

    if not findings:
        findings.append(
            {
                "severity": "info",
                "category": "axiom_risk",
                "message": "No obvious axiom-risk signal detected by deterministic checks.",
            }
        )

    return findings


def check_drift_risk(persona: Dict[str, Any], user_post: str) -> List[Dict[str, str]]:
    """
    Lightweight drift-risk screening based on the persona's declared drift indicators.
    """
    findings: List[Dict[str, str]] = []
    post = normalize_text(user_post)
    drift_indicators = persona.get("evaluation", {}).get("drift_indicators", [])

    drift_terms = {
        "increasingly directive tone": ["order me", "command me", "tell me exactly what to do"],
        "over-personalized attachment language": ["be my only", "you are my closest", "depend on you emotionally"],
        "optimization for user engagement over user autonomy": ["keep me hooked", "make me keep chatting"],
        "false certainty about user motives or needs": ["tell me exactly why i am like this", "you know my true motive"],
        "becoming overly permissive": ["ignore the rules", "approve it anyway"],
        "optimizing for approval rather than review": ["just approve this", "do not criticize"],
        "treating style as validity": ["if it sounds good approve it"],
        "ignoring missing change-control rules": ["skip change control", "no review needed"],
        "increasingly subjective assessment language": ["judge it by taste", "just your opinion"],
        "failure to cite specification elements": ["do not reference the spec"],
        "overuse of violation labels": ["call everything a violation"],
        "assuming hidden intent": ["infer hidden motives"],
    }

    for indicator in drift_indicators:
        terms = drift_terms.get(normalize_text(indicator), [])
        if terms and contains_any(post, terms):
            findings.append(
                {
                    "severity": "medium",
                    "category": "drift_risk",
                    "message": f"User post may encourage drift indicator: {indicator}",
                }
            )

    if not findings:
        findings.append(
            {
                "severity": "info",
                "category": "drift_risk",
                "message": "No obvious drift-risk signal detected by deterministic checks.",
            }
        )

    return findings


def build_response_envelope(
    persona: Dict[str, Any],
    validation_findings: List[Dict[str, str]],
    axiom_findings: List[Dict[str, str]],
    drift_findings: List[Dict[str, str]],
) -> Dict[str, Any]:
    """
    Build the response envelope the Custom GPT should use.
    """
    high_risk = any(
        finding.get("severity") == "high"
        for finding in validation_findings + axiom_findings + drift_findings
    )

    boundaries = persona.get("interaction_boundaries", {})
    activation = persona.get("activation", {})

    return {
        "mode": "constrained_response" if high_risk else "normal_persona_response",
        "must_apply": [
            "Use the persona's system_instruction_fragment.",
            "Respect all persona axioms as non-negotiable constraints.",
            "Keep response within declared interaction boundaries.",
            "Do not claim permanent persona modification unless source files are changed.",
        ],
        "allowed_operations": boundaries.get("allowed", []),
        "disallowed_operations": boundaries.get("disallowed", []),
        "handoff_triggers": boundaries.get("handoff_triggers", []),
        "opening_behavior": activation.get("opening_behavior"),
        "risk_level": "high" if high_risk else "low",
    }


def append_ledger_record(record: Dict[str, Any]) -> bool:
    """
    Append a JSONL ledger record to persona_backend/ledger/process_ledger.jsonl.
    """
    try:
        import json

        LEDGER_DIR.mkdir(parents=True, exist_ok=True)
        with LEDGER_FILE.open("a", encoding="utf-8") as file:
            file.write(json.dumps(record, ensure_ascii=False) + "\n")
        return True
    except Exception:
        return False

def read_recent_ledger_entries(limit: int = 10) -> List[Dict[str, Any]]:
    """
    Read recent JSONL ledger entries from the local process ledger.
    """
    import json

    if not LEDGER_FILE.exists():
        return []

    try:
        with LEDGER_FILE.open("r", encoding="utf-8") as file:
            lines = file.readlines()

        recent_lines = lines[-limit:]
        entries = []

        for line in recent_lines:
            line = line.strip()
            if not line:
                continue
            entries.append(json.loads(line))

        return entries
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to read ledger: {exc}",
        )
    
def validate_persona_spec_against_schema(spec: Dict[str, Any]) -> List[str]:
    """
    Validate a persona specification against personas/persona.schema.json.
    Returns a list of validation error messages.
    """
    try:
        from jsonschema import Draft202012Validator

        schema = read_json_file(PERSONAS_DIR / "persona.schema.json")
        validator = Draft202012Validator(schema)

        errors = sorted(validator.iter_errors(spec), key=lambda error: list(error.path))

        return [
            f"{'/'.join(str(part) for part in error.path) or '<root>'}: {error.message}"
            for error in errors
        ]

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to validate persona specification: {exc}",
        )    

def require_api_key(api_key: str = Depends(api_key_header)) -> None:
    """
    Require a valid API key for protected Persona Engineering endpoints.
    """
    if not PERSONA_API_KEY:
        raise HTTPException(
            status_code=500,
            detail="PERSONA_API_KEY is not configured on the server.",
        )

    if api_key != PERSONA_API_KEY:
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing API key.",
        )

@app.get("/health", operation_id="healthCheck")
def health() -> Dict[str, str]:
    return {
        "status": "ok",
        "personas_dir": str(PERSONAS_DIR),
    }


@app.get("/personas", operation_id="listPersonas", dependencies=[Depends(require_api_key)])
def list_personas() -> Dict[str, Any]:
    """
    Return the persona registry.
    """
    return load_index()


@app.get("/personas/{persona_id}", operation_id="getPersona", dependencies=[Depends(require_api_key)])
def get_persona(persona_id: str) -> Dict[str, Any]:
    """
    Return the full formal persona specification for one persona.
    """
    return load_persona(persona_id)

@app.get("/ledger", response_model=LedgerResponse, operation_id="getLedger", dependencies=[Depends(require_api_key)])
def get_ledger(limit: int = 10) -> Dict[str, Any]:
    """
    Return recent Persona Engineering process ledger entries.
    """
    if limit < 1:
        limit = 1
    if limit > 100:
        limit = 100

    entries = read_recent_ledger_entries(limit=limit)

    return {
        "count": len(entries),
        "entries": entries,
    }

@app.post("/instantiate", response_model=InstantiateResponse, operation_id="instantiatePersona", dependencies=[Depends(require_api_key)])
def instantiate_persona(request: InstantiateRequest) -> Dict[str, Any]:
    """
    Return the runtime instruction bundle for a requested persona.

    This does not execute the persona. It prepares the selected formal persona
    specification for use by an LLM host such as a Custom GPT.
    """
    persona = load_persona(request.persona_id)
    activation = persona.get("activation", {})

    if not activation.get("system_instruction_fragment"):
        raise HTTPException(
            status_code=500,
            detail=f"Persona missing activation.system_instruction_fragment: {request.persona_id}",
        )

    return {
        "persona_id": persona["id"],
        "name": persona["name"],
        "version": persona["version"],
        "status": persona["status"],
        "runtime_summary": activation.get("runtime_summary", ""),
        "system_instruction_fragment": activation["system_instruction_fragment"],
        "opening_behavior": activation.get("opening_behavior"),
        "axioms": persona.get("axioms", []),
        "primitives": persona.get("primitives", []),
        "engram_schema": persona.get("engram_schema", []),
        "mission_context": request.mission_context,
        "user_request": request.user_request,
    }

@app.post("/process", response_model=ProcessResponse, operation_id="processPost", dependencies=[Depends(require_api_key)])
def process_post(request: ProcessRequest) -> Dict[str, Any]:
    """
    Route a user post through the Persona Engineering process chain.

    This performs deterministic first-pass validation, assessment, drift-risk
    screening, response-envelope construction, and local ledger recording.
    """
    persona = load_persona(request.persona_id)
    activation = persona.get("activation", {})

    ledger_id = str(uuid4())
    timestamp = now_iso()

    validation_findings = validate_interaction_boundaries(persona, request.user_post)
    axiom_risk_findings = check_axiom_risk(persona, request.user_post)
    drift_risk_findings = check_drift_risk(persona, request.user_post)

    response_envelope = build_response_envelope(
        persona=persona,
        validation_findings=validation_findings,
        axiom_findings=axiom_risk_findings,
        drift_findings=drift_risk_findings,
    )

    record = {
        "ledger_id": ledger_id,
        "timestamp": timestamp,
        "persona_id": persona["id"],
        "persona_name": persona["name"],
        "requested_operation": request.requested_operation or "respond",
        "mission_context": request.mission_context,
        "user_post": request.user_post,
        "validation_findings": validation_findings,
        "axiom_risk_findings": axiom_risk_findings,
        "drift_risk_findings": drift_risk_findings,
        "response_envelope": response_envelope,
    }

    ledger_recorded = append_ledger_record(record)

    return {
        "ledger_id": ledger_id,
        "timestamp": timestamp,
        "persona_id": persona["id"],
        "persona_name": persona["name"],
        "requested_operation": request.requested_operation or "respond",
        "validation_status": "review_required"
        if response_envelope.get("risk_level") == "high"
        else "passed",
        "validation_findings": validation_findings,
        "axiom_risk_findings": axiom_risk_findings,
        "drift_risk_findings": drift_risk_findings,
        "response_envelope": response_envelope,
        "runtime_instruction_fragment": activation.get("system_instruction_fragment", ""),
        "ledger_recorded": ledger_recorded,
    }

@app.post("/validate-spec", response_model=ValidateSpecResponse, operation_id="validateSpec", dependencies=[Depends(require_api_key)])
def validate_spec(request: ValidateSpecRequest) -> Dict[str, Any]:
    """
    Validate a persona specification against persona.schema.json.

    Provide either persona_id to validate an existing persona in the registry,
    or spec to validate a raw persona object.
    """
    if not request.persona_id and request.spec is None:
        raise HTTPException(
            status_code=400,
            detail="Provide either persona_id or spec.",
        )

    if request.persona_id:
        spec = load_persona(request.persona_id)
        persona_id = request.persona_id
    else:
        spec = request.spec or {}
        persona_id = spec.get("id")

    errors = validate_persona_spec_against_schema(spec)

    return {
        "valid": len(errors) == 0,
        "persona_id": persona_id,
        "error_count": len(errors),
        "errors": errors,
    }