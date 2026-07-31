# Resume Tailoring Phase 3B — Evidence Rubric

Status: Draft

Runtime version: 0.5.0

## Purpose

Phase 3B corrects the Phase 3 mapper behavior that treated every non-empty
lexical match as full requirement support.

## Classification contract

| Classification | Coverage weight | Meaning |
|---|---:|---|
| `strong` | 1.0 | Direct evidence covers the material capability |
| `partial` | 0.5 | Direct evidence covers part of a composite requirement |
| `adjacent` | 0.0 | Transferable or related evidence, but not proof |
| `absent` | 0.0 | No material evidence found |

Only `strong` and `partial` evidence contributes to requirement coverage.
Adjacent evidence remains visible in the evidence map but cannot produce a
passing score. Required absent capabilities force a revision verdict.

## Runtime changes

- Deterministic capability-family classification replaces non-empty lexical
  matching for common résumé requirements.
- Composite requirements expose matched and missing capability components.
- The Assessor emits `pe.resume-assessment.v2`.
- The Assessor reports strong, partial, adjacent, and absent counts.
- Draft selection prioritizes evidence mapped as strong or partial.
- Ledger events contain aggregate classifications, not raw candidate content.

## Governance boundaries

Phase 3B retains all Phase 3A controls:

- exact persona resolution and hashing;
- local-only real-data processing;
- hash-pinned source resolution;
- no external model call or submission;
- no production vector write;
- independent assessment;
- explicit human approval before finalization;
- terminal persona execution attestation only after approval.

## Klain acceptance criterion

The hash-pinned Klain pilot must no longer report 100% coverage. Generic
enterprise integration must not be classified as direct case-management
integration, and regulated-system experience must not be promoted to legal AI
vendor/privacy experience.
