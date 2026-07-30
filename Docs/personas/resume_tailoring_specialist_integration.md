# Resume Tailoring Specialist — Repository-Native Integration Design

## Architectural finding

The repository inspection establishes four distinct mechanisms:

1. `personas/index.json` is the domain-persona registry.
2. `personas/persona.schema.json` defines the repository-native persona shape.
3. Mission Control accepts `pe.mission-control.launch.v1` and requires a
   registered adapter.
4. `MissionLedger` supplies an unrestricted event-type field, ordered
   SHA-256 hash chaining, chain verification, and sealed evidence manifests.

The Resume Tailoring Specialist is therefore registered as a domain persona.
It is not added to the System Persona Registry and it does not approve its own
work.

## Contract projection

The native persona retains the formal model `Pi = <E, P, A>` through:

- `engram_schema` for continuity-bearing governed memory;
- `primitives` for stable cognitive operations;
- `axioms` for non-negotiable behavioral constraints.

The detailed `pe.resume_tailoring.mission.v1` payload is nested inside the
current Mission Control launch envelope:

```text
pe.mission-control.launch.v1
└── tool.parameters.resume_mission
    └── pe.resume_tailoring.mission.v1
```

This preserves compatibility with the current controller while retaining the
resume-domain contract.

## Runtime gap

Mission Control presently treats a mission as one authorization decision
followed by one adapter execution and one terminal state. A live governed
resume transaction requires intermediate pauses:

- unresolved evidence conflict;
- Assessor requires revision;
- awaiting explicit user approval;
- approved post-assessment ingestion.

The production implementation should add a cognitive-workflow adapter and
resume workflow state record rather than disguising these pauses as a Selenium
or JMeter tool process.

## Required resume event types

The existing `MissionLedger.append()` accepts domain-specific event names, so
no new ledger storage format is required. The runtime must emit:

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

The ledger holds hashes, classifications, decisions, and controlled payload
references. Full resume content belongs in the mission evidence directory, not
directly in every JSONL event.

## Ideation ingestion gate

Chunking and embedding may begin only when:

- pre-execution authorization was `AUTHORIZED`;
- the independent Persona Assessor verdict is `pass`;
- the mission ledger chain verifies;
- privacy transformation has removed excluded PII.

User corrections supersede older facts. Unsupported claims become negative
evidence and may prevent recurrence but may never support a future claim.

## Increment sequence

Phase 1 installs the persona and authoritative contracts.

Phase 2 adds:

- `ResumeTailoringAdapter`;
- resume workflow state models;
- approve/revise/resume endpoints;
- Assessor invocation;
- 13 domain ledger events;
- sanitized Context Engineering and Embedding Agent handoff;
- a synthetic fixture and tests.

Phase 3 runs one real job application in shadow mode, compares the governed
artifact against the user's existing tailoring process, and records token,
revision, coverage, and consistency metrics.