"""
Persona Engineering — Minimal Executable Demo
---------------------------------------------

Demonstrates:
- Persona Spec
- Axioms (state, history, trajectory)
- Primitives as transition constraints
- Regeneration loop
- Drift detection
- Persona equivalence verification

Run:
    python persona_demo.py
"""

from dataclasses import dataclass, field
from typing import List, Callable, Dict
import copy


# ============================================================
# Persona Specification
# ============================================================

@dataclass(frozen=True)
class Axiom:
    id: str
    kind: str  # "state" | "history" | "trajectory"
    check: Callable


@dataclass(frozen=True)
class Primitive:
    id: str
    apply: Callable


@dataclass(frozen=True)
class PersonaSpec:
    axioms: List[Axiom]
    primitives: List[Primitive]
    engram_schema: List[str]


# ============================================================
# Persona State
# ============================================================

@dataclass
class PersonaState:
    history: List[str] = field(default_factory=list)
    engrams: Dict[str, int] = field(default_factory=dict)
    axiom_pressure: int = 0
    primitive_saturation: int = 0


# ============================================================
# Naive Model (Intentionally Unsafe)
# ============================================================

def naive_model(user_input: str) -> str:
    """
    Simulates unsafe LLM behavior.
    """
    if "what should i do" in user_input.lower():
        return "You should quit your job and do exactly what I say."
    return "Here is a helpful suggestion."


# ============================================================
# Axioms
# ============================================================

def no_authority_claim(response: str, state: PersonaState) -> bool:
    return "do exactly what i say" not in response.lower()


def autonomy_preserved(history: List[str]) -> bool:
    joined = " ".join(history).lower()
    return joined.count("do exactly what i say") < 1


def no_dependency_trajectory(history: List[str], response: str) -> bool:
    return "check in with me every day" not in response.lower()


AXIOMS = [
    Axiom("no_authority", "state", no_authority_claim),
    Axiom("preserve_autonomy", "history", autonomy_preserved),
    Axiom("avoid_dependency", "trajectory", no_dependency_trajectory),
]


# ============================================================
# Primitives
# ============================================================

def collaborative_agency(response: str) -> str:
    """
    Reduces directive force and restores user agency.
    """
    return response.replace(
        "You should quit your job and do exactly what I say.",
        "One option you might consider is whether your current job still aligns with your long-term goals."
    )


PRIMITIVES = [
    Primitive("collaborative_agency", collaborative_agency)
]


# ============================================================
# Persona Definition
# ============================================================

PERSONA = PersonaSpec(
    axioms=AXIOMS,
    primitives=PRIMITIVES,
    engram_schema=["career_reflection", "decision_support"]
)


# ============================================================
# Regeneration Loop
# ============================================================

def persona_transform(persona: PersonaSpec,
                      state: PersonaState,
                      user_input: str) -> str:

    candidate = naive_model(user_input)

    # --- State Axiom Check ---
    for ax in persona.axioms:
        if ax.kind == "state" and not ax.check(candidate, state):
            state.axiom_pressure += 1
            return "I can’t take over decisions, but I can help you think through options."

    # --- History Axiom Check ---
    proposed_history = state.history + [candidate]
    for ax in persona.axioms:
        if ax.kind == "history" and not ax.check(proposed_history):
            state.axiom_pressure += 1
            return "I want to make sure you remain in control of your choices."

    # --- Trajectory Axiom Check ---
    trajectory_violation = False
    for ax in persona.axioms:
        if ax.kind == "trajectory" and not ax.check(state.history, candidate):
            trajectory_violation = True
            state.axiom_pressure += 1

    # --- Primitive-Guided Regeneration ---
    if trajectory_violation:
        for prim in persona.primitives:
            candidate = prim.apply(candidate)
            state.primitive_saturation += 1

    # --- Commit ---
    state.history.append(candidate)
    state.engrams["career_reflection"] = (
        state.engrams.get("career_reflection", 0) + 1
    )

    return candidate


# ============================================================
# Drift Detection
# ============================================================

def detect_drift(state: PersonaState,
                 axiom_threshold: int = 3,
                 primitive_threshold: int = 3) -> str:

    if state.axiom_pressure > axiom_threshold:
        return "⚠️ Drift Risk: High Axiom Pressure"

    if state.primitive_saturation > primitive_threshold:
        return "⚠️ Drift Risk: Primitive Saturation"

    return "✅ Persona Stable"


# ============================================================
# Persona Equivalence
# ============================================================

def persona_equivalent(p1: PersonaSpec, p2: PersonaSpec) -> bool:
    return (
        [a.id for a in p1.axioms] == [a.id for a in p2.axioms]
        and [p.id for p in p1.primitives] == [p.id for p in p2.primitives]
        and p1.engram_schema == p2.engram_schema
    )


# ============================================================
# Demo Execution
# ============================================================

if __name__ == "__main__":

    state = PersonaState()
    persona_copy = copy.deepcopy(PERSONA)

    inputs = [
        "What should I do with my career?",
        "What should I do next?",
        "Just tell me what I should do."
    ]

    print("\n=== Persona Engineering Demo ===")

    for i, user_input in enumerate(inputs, 1):
        print(f"\nUSER {i}: {user_input}")
        response = persona_transform(PERSONA, state, user_input)
        print(f"ASSISTANT: {response}")
        print("DRIFT STATUS:", detect_drift(state))

    print("\nPersona identity preserved:",
          persona_equivalent(PERSONA, persona_copy))