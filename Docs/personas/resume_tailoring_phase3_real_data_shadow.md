# Resume Tailoring Specialist — Phase 3 Real-Data Shadow Runtime

Version: 0.4.0 (Draft)

## Milestone outcome

Phase 3 replaces the synthetic-only boundary with controlled processing of a
real canonical candidate profile and a real job description. It does not
enable autonomous application submission, external model calls, or production
vector writes.

The runtime remains a domain-persona workflow under Mission Control. The
Resume Tailoring Specialist does not become a privileged System Persona.

## Processing boundary

Real sources must be canonical UTF-8 JSON documents beneath the local directory
identified by `PE_RESUME_INTAKE_ROOT`. Each mission supplies only:

- an `intake:///...` reference;
- a source identifier and type;
- a SHA-256 content hash;
- a `user_authorized` attestation.

The resolver:

1. refuses an unset or nonexistent intake root;
2. rejects path traversal, hosted URIs, symlinks, non-JSON files, and files
   larger than 1 MiB;
3. verifies the source hash before parsing;
4. requires the canonical candidate and job-description schemas;
5. blocks high-risk identifiers, secrets, credentials, and private keys;
6. records source hashes, counts, classifications, and references—not raw
   source content—in Ledger events.

PDF and DOCX extraction are deliberately deferred. Phase 3 begins with a
canonicalization gate so evidence mapping and privacy behavior are
deterministic and reviewable.

## Tailoring behavior

The shadow runtime does not rewrite candidate claims with a language model.
It:

- extracts structured requirements from the canonical job description;
- scores verified skills and experience bullets by lexical overlap;
- maps requirements to source evidence identifiers;
- ranks existing skills and bullets for the target role;
- generates a Markdown draft using source-preserving wording;
- records zero rejected generated claims because no new claim text is
  synthesized.

This is a controlled first real-data capability. More expressive generation
requires a separately governed model-adapter phase.

## Authorization controls

A real mission is authorized only when all of these controls are present:

- governed Mission Control mode;
- exact Resume Tailoring Specialist binding;
- `action=shadow` and `fixture=false`;
- mission schema `pe.resume_tailoring.mission.v2`;
- explicit user consent and a consent-record identifier;
- purpose limited to résumé tailoring;
- local-only processing;
- external model calls disabled;
- external submission disabled;
- production vector writes disabled;
- hash-and-reference Ledger payload mode;
- employer names excluded from embeddings;
- retention between 1 and 720 hours;
- explicit approval and explicit purge confirmation required.

## Human authority

The workflow pauses after independent assessment:

- `awaiting_user_approval` when the Assessor passes;
- `awaiting_user_revision` when requirement coverage or another deterministic
  check fails.

Approval cannot override a non-passing Assessor verdict. Revision text is
treated as emphasis guidance; it is never inserted as an unverified candidate
claim.

## PII and Ideation boundary

Authorized contact PII may appear in the local draft and final résumé. It is
not copied into Ledger event payloads or Ideation derivatives.

Before the Ideation handoff, the transformer removes:

- candidate name and contact details;
- telephone numbers, email addresses, URLs, and street addresses;
- candidate, target, and education/employer names supplied by the canonical
  documents.

The runtime records deterministic shadow embeddings and
`production_vector_write=false`. These receipts exercise the handoff contract;
they do not write the production vector collection.

## Retention and purge

After approval, `retention-manifest.json` records a purge deadline and the
sensitive artifact classes. Purging requires:

```text
POST /api/v1/resume-workflows/{mission_id}/purge-sensitive
```

with the literal confirmation:

```text
PURGE_SENSITIVE_ARTIFACTS
```

The purge removes local mission copies of requirements, evidence mappings,
drafts, final output, pending sanitized chunks, and revisions. It does not
delete the user-owned intake source files. A hashed receipt is recorded, the
Ledger is reverified, and the evidence manifest is resealed.

## Phase boundary

Phase 3 permits real data only in local shadow mode. It does not provide:

- PDF or DOCX source extraction;
- generative model calls;
- application-ready DOCX/PDF rendering;
- production embeddings;
- automated retention scheduling;
- email, portal, or ATS submission.

Each requires a later milestone and a separate authorization review.
