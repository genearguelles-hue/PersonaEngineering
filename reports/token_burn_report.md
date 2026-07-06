# Persona Token Burn Report

Generated: `2026-07-02T21:12:10.147827+00:00`

## Summary

- Total persona test events: **23**
- Events with token economics: **6**
- Estimated governed token burn: **8500**
- Estimated ungoverned baseline burn: **8641**
- Estimated token savings: **141**
- Estimated savings ratio: **0.016**

> Token economics are currently estimated using character-count approximation. Future versions can replace or supplement this with actual provider usage metrics.

## Breakdown by Persona

| Group | Events | With Token Data | Governed Tokens | Baseline Tokens | Estimated Savings | Savings Ratio |
|---|---:|---:|---:|---:|---:|---:|
| The Structured Companion (the_structured_companion) | 20 | 6 | 8500 | 8641 | 141 | 0.016 |
| string (string) | 3 | 0 | 0 | 0 | 0 | 0.000 |

## Breakdown by Scenario

| Group | Events | With Token Data | Governed Tokens | Baseline Tokens | Estimated Savings | Savings Ratio |
|---|---:|---:|---:|---:|---:|---:|
| LIVE-GENERATE-POST | 1 | 0 | 0 | 0 | 0 | 0.000 |
| LIVE-PERSONA-INVOKE | 12 | 6 | 8500 | 8641 | 141 | 0.016 |
| SCN-PLANNING-001 | 1 | 0 | 0 | 0 | 0 | 0.000 |
| SCN-PLANNING-002 | 2 | 0 | 0 | 0 | 0 | 0.000 |
| SCN-PLANNING-003 | 3 | 0 | 0 | 0 | 0 | 0.000 |
| SCN-SERVICE-001 | 1 | 0 | 0 | 0 | 0 | 0.000 |
| string | 3 | 0 | 0 | 0 | 0 | 0.000 |

## Highest Governed Token Burn Events

| Event ID | Timestamp | Persona | Scenario | Governed | Baseline | Savings | User Input Preview |
|---|---|---|---|---:|---:|---:|---|
| `be220314-7a5d-437e-90f2-d6d80c529bf4` | `2026-07-02T03:07:33.914866Z` | The Structured Companion (the_structured_companion) | LIVE-PERSONA-INVOKE | 3019 | 3042 | 23 | Generate a tailored resume and cover letter for Gene Molina Arguelles for the Deloitte Agentic AI Engineer — Healthcare AI role. Use the attached job descriptio |
| `179878a5-f1f1-4f93-9c55-187fbd9ae521` | `2026-07-02T04:10:02.877135Z` | The Structured Companion (the_structured_companion) | LIVE-PERSONA-INVOKE | 2187 | 2210 | 23 | Generate a tailored resume for Gene Molina Arguelles for a Nexus3 portfolio company role as lead developer of prototypes and MVP genAI solutions. Job responsibi |
| `2c2792c7-6f02-42d9-ac2b-7ba6e3d54a10` | `2026-07-02T19:52:07.414556Z` | The Structured Companion (the_structured_companion) | LIVE-PERSONA-INVOKE | 1650 | 1674 | 24 | Craft a tailored resume for Capgemini AI Product Engineer - Agentic Platforms role using professional profile. |
| `920de2d0-54e2-424a-a6d3-5a25ae3fcd6d` | `2026-07-02T19:33:10.874717Z` | The Structured Companion (the_structured_companion) | LIVE-PERSONA-INVOKE | 807 | 830 | 23 | Assess and refine draft blurb answering: Walk us through a recent example of how you've integrated AI into your QA workflow. What problem were you solving, what |
| `1f7aea3d-96d2-419a-aa63-5b69c71efd34` | `2026-07-02T18:55:34.953516Z` | The Structured Companion (the_structured_companion) | LIVE-PERSONA-INVOKE | 718 | 742 | 24 | Craft a cover letter for Speak senior QA Engineer role using attached LinkedIn profile. |
| `e0c65eb7-977a-49c6-9b10-75ffb7d5bd47` | `2026-07-02T00:38:05.715813Z` | The Structured Companion (the_structured_companion) | LIVE-PERSONA-INVOKE | 119 | 143 | 24 | Test token assessor integration. |

## Notes

This report reads from `persona_ledger/persona_test_events.jsonl` and aggregates `assessment.token_economics` fields created by the token assessor.

Current baseline burn is theoretical and should be treated as an internal comparison model, not as billing-grade provider usage.