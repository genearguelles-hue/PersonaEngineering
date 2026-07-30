# Resume Tailoring Specialist — Phase 2 Runtime

Version: 0.3.1 (Draft)

The 0.3.1 installer normalizes line endings and final-newline variants while
comparing the reviewed adapter registry. Any substantive import or export
difference still fails closed.

## Scope

Phase 2 installs a synthetic-only governed cognitive workflow around the
Phase 1 `pe.resume_tailoring_specialist` persona and
`pe.resume_tailoring.mission.v1` contract.

The workflow is separate from Mission Control's generic one-shot tool path.
The generic path is terminal; résumé tailoring must pause after independent
assessment and wait for an explicit human decision.

## Runtime sequence

1. Receive the Mission Control launch envelope.
2. Require governed mode, the exact persona binding, the `resume-tailor`
   adapter, the `smoke` action, and `fixture=true`.
3. Resolve only synthetic source references.
4. Extract synthetic job requirements.
5. Map each requirement to authorized evidence.
6. reject and hash an unsupported claim.
7. Generate a draft.
8. Invoke the independent deterministic Resume Persona Assessor.
9. Pause at `awaiting_user_approval`.
10. Accept a controlled revision or an approval.
11. Finalize only after a passing Assessor verdict and explicit approval.
12. Produce sanitized chunks and deterministic fixture embeddings.
13. Verify the hash chain and seal the evidence manifest.

## Human decision endpoint

Use:

```text
POST /api/v1/resume-workflows/{mission_id}/decision
```

A revision requires at least one correction. Approval cannot include
corrections. User approval cannot override a non-passing Assessor verdict.

## Ledger coverage

The implementation recognizes exactly these résumé-domain event types:

1. `resume_mission_received`
2. `resume_authorization_decided`
3. `resume_sources_resolved`
4. `resume_requirements_extracted`
5. `resume_evidence_mapped`
6. `resume_claim_rejected`
7. `resume_draft_generated`
8. `resume_assessment_completed`
9. `resume_user_revision_received`
10. `resume_artifact_finalized`
11. `resume_ideation_chunks_prepared`
12. `resume_ideation_embeddings_recorded`
13. `resume_mission_terminal`

Draft and assessment events may repeat after revision. Ledger event payloads
contain hashes, counts, decisions, and artifact references—not complete résumé
content.

## Ideation boundary

Phase 2 does not write to the production Chroma collection. It creates:

- `ideation-chunks.sanitized.json`;
- `ideation-embedding-manifest.json`;
- a `resume_ideation_embeddings_recorded` receipt.

The deterministic eight-dimensional fixture vectors validate the handoff
contract without claiming production embedding-model use. The manifest records
`production_vector_write=false`.

The pipeline rejects email addresses, common telephone forms, Social Security
number forms, and secret/token markers. The unsupported Kubernetes claim is
retained as hashed negative evidence and is not admitted into positive
embedding vectors.

## Phase boundary

Phase 2 permits synthetic fixture data only. A real résumé, CV, job
description, email address, phone number, street address, or other candidate
data must not be submitted.

Phase 3 will require a separate shadow-mode authorization and a reviewed
production source resolver, document generator, privacy transformer, embedding
adapter, and token-telemetry implementation.
