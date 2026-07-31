# Phase 3A — Persona Execution Attestation

Status: Draft
Runtime version: 0.4.1
Parent milestone: Phase 3 real-data shadow runtime (`4836622`)

## Purpose

Phase 3A closes the distinction between a workflow that merely names the
Resume Tailoring Specialist and a workflow that proves which persona
specification governed execution.

The runtime resolves the exact `pe.resume_tailoring_specialist@0.1.0`
specification from the repository persona store. It validates the persona
runtime contract and hashes the exact persona bytes, runtime contract,
engrams, primitives, and axioms before authorization proceeds.

## Evidence chain

Each governed mission adds:

1. `persona-binding.json`
2. `persona_binding_resolved` in `events.jsonl`
3. `persona-execution-attestation.json`
4. Both attestation artifacts in the sealed `evidence-manifest.json`

The binding event is inserted after `resume_mission_received` and before
`resume_authorization_decided`. Its event hash is copied into the terminal
attestation.

## Attestation content

The execution attestation records:

- Mission ID
- Persona ID and version
- Exact persona specification SHA-256
- Persona model: `Pi = <E, P, A>`
- Runtime-contract SHA-256
- Active engram, primitive, and axiom IDs
- Binding-event sequence and hash
- Authorization outcome
- Independent assessor identity and verdict
- Explicit-approval state
- Current Ledger validity, event count, and terminal hash
- Mission-terminal event hash
- Final résumé artifact SHA-256

The attestation is written only after the terminal Ledger event verifies. It is
then included in the sealed evidence manifest, avoiding a circular dependency
between the attestation and Ledger hash.

## Persona Registry behavior

Resolution is dynamic and fail-closed:

- The repository `personas/` store is indexed by exact persona ID and version.
- No match blocks attestation.
- Multiple matches block attestation.
- A mismatched runtime contract blocks attestation.
- Duplicate E/P/A component IDs block attestation.
- When `personas/index.json` registers the same ID and version, its file mapping
  is cross-checked and recorded as verified.

The registry index is not modified by this milestone. This preserves unrelated
local registry work.

## Purge continuity

The governed purge removes sensitive résumé artifacts but retains:

- The original final résumé SHA-256
- The persona-binding evidence
- The persona-execution attestation
- The append-only Ledger

After a purge event, the attestation is regenerated so its Ledger-head hash
matches the new chain while the original résumé hash remains provable.

## Operational boundary

Phase 3A does not add external model calls, employer submission, recruiter
contact, production vector writes, PDF/DOCX ingestion, or fabricated claims.
The output remains local Markdown in real-data shadow mode and still requires
an independent assessor pass plus explicit user approval.
