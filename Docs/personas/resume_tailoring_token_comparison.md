# Résumé Tailoring Matched-Pair Token Comparison

## Purpose

This runtime supplies the missing operational proof in the résumé-tailoring
demonstration:

1. the `pe.resume_tailoring_specialist` persona supervises the governed arm;
2. every provider call produces canonical token telemetry;
3. one comparator reports governed versus ungoverned consumption without
   hiding planning, assessment, or repair overhead.

## Controlled variables

Both arms freeze candidate-source hash, job-source hash, model, reasoning
effort, maximum output tokens, shared task contract, and output format. The
execution order is deterministically balanced from the pair ID unless the
operator explicitly fixes it.

The behavioral treatment is the governance layer:

| Arm | Task call | Persona plan | Independent review | Repair |
|---|---:|---:|---:|---:|
| Governed | 1 | 1 | 1 or 2 | 0 or 1 |
| Ungoverned | 1 | 0 | 0 | 0 |

## Accounting

Primary totals are:

```text
T_governed = T_task + T_governance + T_repair
T_ungoverned = T_task
delta = T_ungoverned - T_governed
change_percent = delta / T_ungoverned * 100
```

Positive change means the governed arm used fewer tokens. Negative change
means governance consumed more tokens. Reasoning tokens are reported as a
subset of provider output tokens and are not added to `total_tokens` a second
time.

The blind evaluator's usage is preserved under the `evaluation` category but
excluded from both primary totals. This keeps quality control visible without
changing the treatment comparison.

## Evidence and privacy

The Ledger stores source hashes, prompt hashes, output hashes, provider usage,
and hashed provider-response IDs. It does not store candidate or employer text.
Private output résumés and assessment files remain under the operator-selected
run directory outside Git. The OpenAI request sets `store=false`; external
submission and production-vector writes remain false.

The operator must supply an explicit consent-record ID. The runtime hashes that
identifier before writing it to the Ledger.

## Interpretation limit

The first real matched pair is a mechanism demonstration. Statistical claims
require the larger predeclared matched-pair program; the runtime writes this
limitation into both the comparison and terminal Ledger event.
