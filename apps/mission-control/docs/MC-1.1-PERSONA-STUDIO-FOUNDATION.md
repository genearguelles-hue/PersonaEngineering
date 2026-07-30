# MC-1.1 — Persona Studio Foundation

## Outcome

MC-1.1 repairs the Selenium evidence-vocabulary mismatch and introduces the
first governed behavioral-correction surface in Persona Engineering Mission
Control.

## Selenium result contract

The live Selenium CLI emits `pe.test-run.envelope.v1` with:

- `summary.tests`
- `summary.failures`
- `summary.errors`
- `summary.skipped`
- `summary.testcases[].time_seconds`

The authoritative assessor previously read only `summary.passed`,
`summary.failed`, and `summary.duration_seconds`. A successful run containing
two passed tests was therefore assessed as zero passed tests.

The compatibility patch normalizes the existing envelope without changing its
meaning. Mission Control independently verifies and seals the normalized
summary as `pe.selenium-result-contract-verification.v1`.

## Behavioral incidents

`pe.behavioral-incident.v1` is an explicitly created record of observed persona
behavior. It is not created automatically when a tool, process, network call,
contract translation, or execution environment fails.

An incident may link to a mission and evidence references, but it requires an
operator to classify and describe the behavioral deviation.

## Persona delta proposals

`pe.persona-delta-proposal.v1` binds:

- one behavioral incident;
- a persona and immutable base version;
- a distinct candidate version;
- one or more primitive changes;
- safety constraints;
- regression objectives;
- a human review history.

The proposal API supports `approve` and `reject`. Approval records governance
consent for a candidate; it never mutates or activates a persona.

There is deliberately no apply endpoint in MC-1.1.

## Version and regression views

Persona Studio displays:

- active baseline versions;
- proposed, approved, or rejected candidate versions;
- primitive before/after differences;
- baseline-to-candidate regression metrics;
- immutable review outcomes;
- the invariant `application_status: not_applied`.

All incident, proposal, review, and regression operations are appended to the
hash-chained persona-governance audit log.
