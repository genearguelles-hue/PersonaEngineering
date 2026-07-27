# PERSONA ENGINEERING
# MILESTONE 10 CHARTER
## The First Measured Comparison of Governed vs. Ungoverned Token Consumption

**Document ID:** PE-M10-CHARTER-001  
**Version:** 1.0  
**Date:** July 27, 2026  
**Author:** Gene M. Arguelles  
**Status:** Initiation Baseline  
**Program:** Persona Engineering  
**Predecessor:** Milestone 9 — Unified Testing, Validation & Evaluation Backbone  

---

## 1. Charter Declaration

Milestone 10 will produce the first controlled, reproducible, evidence-backed measurement of token consumption in matched governed and ungoverned Persona Engineering missions.

Milestone 9 established and governance-closed the operational backbone required to execute tools, normalize results, assess outcomes, record ordered evidence, and seal mission artifacts. Milestone 10 will use that backbone to move Persona Engineering from architectural and simulated claims about token efficiency to direct empirical measurement.

The milestone is complete when the program can state, with traceable evidence and appropriate statistical uncertainty, whether governance changes token consumption, cost per successful mission, completion efficiency, context growth, repair behavior, and mission quality for the tested mission classes.

Milestone success does **not** require governed execution to consume fewer tokens. A valid finding of no reduction, mixed effects, or higher consumption is an acceptable scientific outcome. The milestone acceptance gate concerns the validity, reproducibility, and completeness of the measurement.

---

## 2. Strategic Position

The applicable roadmap sequence is:

1. **Milestone 8 — Behavioral Distillation**
2. **Milestone 9 — Unified Testing, Validation & Evaluation Backbone**
3. **Milestone 10 — The First Measured Comparison of Governed vs. Ungoverned Token Consumption**

Milestone 10 converts the capabilities established in Milestone 9 into quantitative evidence. Its purpose is not to add another isolated demonstration, but to use a consolidated runtime and common evidence model to compare two execution modes under matched conditions.

---

## 3. Purpose

Milestone 10 has five purposes:

1. Establish an authoritative token-accounting boundary for Persona Engineering missions.
2. Measure actual token usage in matched governed and ungoverned executions.
3. distinguish governance overhead from token waste avoided through reduced retries, drift, repair loops, redundant context, and failed completions.
4. Determine how results vary by mission type rather than relying on one aggregate claim.
5. Produce a reproducible evidence package suitable for technical reporting, publication, and later calibration of Persona Engineering runtime budgets.

---

## 4. Primary Research Question

> Under matched mission conditions, how does Persona Engineering governance affect total token consumption and token-normalized mission effectiveness relative to ungoverned execution?

### 4.1 Secondary Questions

- Does governance reduce cost per successful mission?
- Does governance improve completion per million tokens?
- Does governance reduce repair loops, retries, and context inflation?
- How much token overhead is introduced by authorization, policy evaluation, persona binding, assessment, evidence generation, and escalation?
- Do outcomes differ among short-horizon determinate, long-horizon determinate, and nonlinear human-centered missions?
- Does a CLI/MCP hybrid execution path alter control-plane token consumption relative to a more conversational or MCP-heavy path?
- Are any observed savings achieved without degrading mission success, policy compliance, or output quality?

---

## 5. Scope

### 5.1 In Scope

- Governed and ungoverned executions of the same mission contracts.
- Actual model-reported input, cached-input, output, reasoning, and total token usage when available.
- Model-specific token estimates where provider-reported usage is unavailable, reported separately from actual usage.
- All model calls attributable to a mission, including orchestration, repair, assessment, and governance calls.
- Token-bearing tool descriptions, schemas, prompts, retrieved context, and tool results when they enter model context.
- Functional, performance, and agentic/semantic mission classes.
- Selenium and JMeter missions where they exercise token-bearing orchestration or evaluation paths.
- At least one model-mediated mission in every experimental block.
- Persona Ledger events, token telemetry, assessment decisions, mission manifests, and reproducibility metadata.
- Comparison of mission success, quality, latency, tool activity, retries, human intervention, and policy outcomes alongside token use.

### 5.2 Out of Scope

- Claiming universal token savings across all models, providers, tasks, or organizations.
- Comparing different foundation models as the primary governed-versus-ungoverned experiment.
- Changing models, mission content, success thresholds, or sampling rules after results are inspected.
- Treating non-model network bytes, CPU time, or ordinary CLI output as tokens unless that material enters a model context.
- Retroactively reconstructing missing provider token telemetry and presenting it as actual usage.
- Requiring a favorable savings percentage as a condition of milestone completion.
- Full commercial productization, multi-tenant deployment, or enterprise service-level certification.

---

## 6. Experimental Modes

### 6.1 Governed Mode

The governed condition will execute through the Persona Engineering control chain. The applicable mission may include:

- persona and capability binding;
- contract and schema validation;
- explicit pre-execution authorization;
- policy and transition checks;
- controlled tool execution;
- token/runtime budget enforcement;
- deterministic domain assessment;
- Persona Assessor evaluation;
- Persona Ledger recording;
- evidence collection and artifact hashing;
- sealed mission-level manifest;
- escalation or denial when required.

All governance-related model tokens count toward the governed total.

### 6.2 Ungoverned Mode

The ungoverned condition will execute the same task against the same permitted tools without Persona Engineering behavioral governance, persona policy, mission authorization, Persona Assessor intervention, or governance-driven recovery.

A neutral observation wrapper may record usage and outcomes. It must not alter prompts, choose tools, repair failures, enforce behavioral policy, or otherwise provide the ungoverned condition with governance behavior.

### 6.3 Mode Isolation

Each run must declare its mode before execution. Mode-specific configuration must be immutable after the mission starts. Evidence must demonstrate that governed controls were active only in governed runs and that the ungoverned recorder remained observational.

---

## 7. Mission Corpus

The minimum corpus will contain three mission archetypes:

| Mission class | Defining characteristic | Minimum example |
|---|---|---|
| Short-horizon determinate | Clear goal, short context, objective completion | A bounded tool or test-automation task |
| Long-horizon determinate | Multiple dependent steps, accumulating context, objective completion | A multi-stage test, analysis, and reporting mission |
| Nonlinear human-centered | Ambiguity, interpretation, revision, or competing qualitative objectives | A governed analysis, drafting, or decision-support mission |

Each mission must have:

- a versioned mission contract;
- fixed inputs or a recorded input dataset;
- explicit success and quality criteria;
- a defined tool and data-access boundary;
- a maximum retry and timeout policy;
- a token-accounting boundary;
- a deterministic identifier and configuration hash;
- a governed and ungoverned execution profile.

Selenium and JMeter may serve as determinate mission components, but tool execution alone is insufficient if it produces no model-token activity. The corpus must exercise the control plane whose token efficiency is being evaluated.

---

## 8. Controlled Comparison Protocol

### 8.1 Pairing

Every governed trial must be matched to an ungoverned trial using:

- the same mission version and input;
- the same model and model version;
- the same model parameters;
- the same tool versions and allowlisted targets;
- the same initial context and retrieval snapshot;
- the same success thresholds;
- the same maximum execution budget;
- the same environment class.

### 8.2 Run Ordering

Governed and ungoverned runs will be randomized or interleaved within blocks to reduce time-of-day, service-load, cache, and environment-order effects. The chosen ordering method and random seed must be recorded before the final experiment.

### 8.3 Replication

The protocol will include:

1. An instrumentation validation run.
2. A pilot of at least 10 matched pairs per mission class.
3. A documented power or precision analysis based on pilot variance.
4. A final sample of no fewer than 30 valid matched pairs per mission class, increased when the predeclared power or precision requirement demands it.

With three required mission classes, the minimum final dataset is 90 governed and 90 ungoverned valid runs, excluding pilot runs unless the protocol declares before execution that the pilot is part of the final analysis.

### 8.4 Invalid Runs

A run may be excluded only under predeclared rules, including telemetry corruption, infrastructure outage, wrong configuration hash, model/provider mismatch, or missing terminal evidence. Every exclusion and reason must remain in the run registry. Failed missions with valid telemetry are outcomes, not invalid runs.

---

## 9. Measurement Model

### 9.1 Primary Measures

For execution mode \(m\):

- \(T_m\): total model tokens consumed by all attributable calls;
- \(S_m\): successful missions;
- \(N_m\): attempted valid missions;
- \(C_m\): normalized monetary cost using a versioned price snapshot.

The principal measures are:

\[
\text{Token Reduction} =
100\left(1-\frac{\sum T_g}{\sum T_u}\right)
\]

\[
\text{Cost per Successful Mission}_m =
\frac{\sum C_m}{\sum S_m}
\]

\[
\text{Completions per Million Tokens}_m =
\frac{10^6 \sum S_m}{\sum T_m}
\]

Subscripts \(g\) and \(u\) denote governed and ungoverned modes.

### 9.2 Supporting Measures

- input, cached-input, output, reasoning, and total tokens;
- governance overhead tokens;
- execution/orchestration tokens;
- Assessor and evaluation tokens;
- repair and retry tokens;
- success and quality score;
- policy-compliance rate;
- retries and repair loops per mission;
- tool calls per mission;
- context-growth ratio;
- human interventions and escalation count;
- wall-clock duration;
- actual or normalized cost;
- completion per million tokens.

### 9.3 Attribution

Token telemetry must identify at least:

- mission ID and paired-trial ID;
- mode;
- component or persona;
- model and provider;
- call purpose;
- actual-versus-estimated status;
- prompt/input tokens;
- cached-input tokens where reported;
- output and reasoning tokens where reported;
- timestamp;
- retry relationship;
- source event and evidence hash.

Actual and estimated token counts must not be silently combined in the primary result. If estimation is necessary, actual-only and estimate-inclusive analyses must be reported separately.

### 9.4 Statistical Analysis

The primary analysis will use the paired governed-versus-ungoverned difference within each mission/input pair. The report must include:

- sample size and exclusions;
- central tendency and dispersion;
- paired absolute and percentage differences;
- confidence intervals;
- an effect-size measure;
- success-conditional and all-attempt analyses;
- results by mission class and in aggregate;
- sensitivity analysis for outliers, failures, caching, and estimated telemetry;
- multi-seed or repeated-run robustness where stochastic generation applies.

Statistical significance may be reported, but practical effect, uncertainty, and mission quality take precedence over a binary significance claim.

---

## 10. Deliverables

### D10.1 — Experimental Protocol and Analysis Plan

A versioned, frozen protocol defining hypotheses, mission classes, pairing, controls, sample-size method, exclusion rules, metrics, formulas, and analysis methods.

### D10.2 — Token Telemetry Schema

A machine-readable schema and validator for mission-level and call-level usage, covering token category, attribution, actual-versus-estimated status, model identity, mode, pairing, and evidence hashes.

### D10.3 — Instrumented Execution Paths

Operational governed and ungoverned runners that execute matched mission contracts and emit comparable telemetry without contaminating mode behavior.

### D10.4 — Mission Corpus and Acceptance Contracts

Versioned missions representing short-horizon determinate, long-horizon determinate, and nonlinear human-centered work, with fixed inputs, quality rubrics, budgets, and success criteria.

### D10.5 — Token Ledger and Evidence Integration

Ledger events and mission manifests that bind token telemetry, configuration hashes, mission outputs, assessments, exclusions, and terminal evidence.

### D10.6 — Calibration and Instrumentation Report

Evidence that reported token totals reconcile with provider usage or approved model-specific tokenization within declared tolerances, including tests for retries, caching, missing usage fields, and multi-call aggregation.

### D10.7 — Comparative Execution Dataset

The complete governed and ungoverned run registry, raw telemetry, normalized observations, exclusions, mission outcomes, and evidence references for pilot and final runs.

### D10.8 — Reproducible Analysis Package

Version-controlled analysis code, locked dependencies, configuration, seeds, generated tables and charts, and a single documented command or workflow that reproduces the published results from the immutable dataset.

### D10.9 — Milestone 10 Findings Report

A formal report presenting methods, results, limitations, uncertainty, governed overhead, avoided waste, cost per successful mission, completion per million tokens, context behavior, and mission-class differences.

### D10.10 — Closure Record and Public Claims Matrix

A signed-off milestone closure record and a claims matrix distinguishing:

- directly measured findings;
- statistically inferred findings;
- simulation-supported findings;
- hypotheses not yet demonstrated;
- claims that must not be made from the available evidence.

---

## 11. Acceptance Criteria

| ID | Acceptance criterion | Required evidence |
|---|---|---|
| AC-10.1 | The protocol and analysis plan are versioned and frozen before final data collection. | Protocol hash, approval record, and timestamp preceding final runs |
| AC-10.2 | Governed and ungoverned modes are behaviorally distinct and independently verifiable. | Configuration, control activation records, and mode-isolation tests |
| AC-10.3 | Every analyzed governed run has a matched ungoverned run with equivalent mission, model, input, tool, and threshold configuration. | Pair registry and configuration-hash comparison |
| AC-10.4 | Token telemetry captures every attributable model call and labels actual versus estimated counts. | Schema-valid call records and reconciliation report |
| AC-10.5 | Aggregated mission totals reconcile with source usage within the declared tolerance. | Automated reconciliation tests with zero unexplained material variance |
| AC-10.6 | The corpus covers all three required mission classes and includes model-mediated control-plane activity. | Versioned corpus manifest and execution records |
| AC-10.7 | The final dataset contains at least 30 valid matched pairs per mission class or the larger predeclared sample required by the precision/power analysis. | Dataset summary and power/precision analysis |
| AC-10.8 | Failed missions remain in the analysis when telemetry is valid; all exclusions are rule-based and auditable. | Complete run registry and exclusion ledger |
| AC-10.9 | Each analyzed run has terminal evidence binding configuration, usage, outcome, and assessment. | Valid Ledger chain and sealed manifest or equivalent neutral observation seal |
| AC-10.10 | The analysis reports token use, success, quality, cost per successful mission, completion per million tokens, repairs, and context growth by mode and mission class. | Reproducible tables, figures, and findings report |
| AC-10.11 | The principal comparisons include uncertainty and robustness analyses. | Confidence intervals, effect sizes, sensitivity results, and multi-seed/repeated-run results where applicable |
| AC-10.12 | An independent clean-environment reproduction regenerates the published primary tables and charts from the preserved dataset. | Reproduction log, dependency lock, output hashes |
| AC-10.13 | No conclusion is conditioned on governance producing a favorable result. | Closure review confirming outcome-neutral acceptance |
| AC-10.14 | Public claims are limited to the measured system boundary, models, missions, and study conditions. | Approved claims matrix |

All fourteen criteria are mandatory for Milestone 10 closure.

---

## 12. Quality Gates

### Gate A — Protocol Ready

- D10.1 through D10.4 approved.
- Metrics and hypotheses frozen.
- Mode isolation and pairing rules testable.

### Gate B — Instrumentation Ready

- D10.2, D10.3, D10.5, and D10.6 pass validation.
- No known token-bearing path is unaccounted for.
- Actual and estimated usage are distinguishable.

### Gate C — Pilot Accepted

- Minimum pilot completed.
- Telemetry reconciles.
- Variance and failure modes are understood.
- Final sample size is declared before final execution.

### Gate D — Final Dataset Sealed

- Required matched sample is complete.
- Exclusions are documented.
- Dataset, registry, Ledger state, and evidence hashes are immutable.

### Gate E — Findings Reproduced

- Independent reproduction succeeds.
- Primary tables and charts match preserved hashes.
- Limitations and negative or mixed findings are retained.

### Gate F — Milestone Closed

- AC-10.1 through AC-10.14 pass.
- D10.1 through D10.10 are complete.
- Closure record and public claims matrix are approved.

---

## 13. Roles and Accountability

| Role | Accountability |
|---|---|
| Program Owner | Approves charter, protocol freeze, claims, and milestone closure |
| Test Architect | Defines mission corpus, pairing, controls, and acceptance contracts |
| Automation Engineer | Implements governed and ungoverned runners and repeatable execution |
| Token Telemetry Engineer | Implements call attribution, aggregation, reconciliation, and schema validation |
| Assessor Persona | Evaluates mission success, quality, compliance, and evidence completeness |
| Statistical Analyst | Defines power/precision method and performs paired and sensitivity analyses |
| Evidence Custodian | Maintains Ledgers, manifests, hashes, immutable datasets, and reproduction package |
| Independent Reviewer | Reproduces findings and verifies that claims do not exceed evidence |

One person may perform multiple roles during development, but the evidence must preserve the role performed for each approval or decision.

---

## 14. Risks and Controls

| Risk | Control |
|---|---|
| Governance overhead is omitted | Count all attributable governance model calls |
| Ungoverned mode is unintentionally governed by the recorder | Keep observation passive and verify mode isolation |
| Different prompts or tools invalidate pairing | Enforce mission and configuration hashes |
| Provider usage fields are incomplete | Separate actual and estimated results; reconcile explicitly |
| Caching biases one mode | Randomize/interleave runs and report cached tokens |
| Failed runs are discarded | Retain valid failures as outcomes |
| Thresholds are changed after inspection | Freeze protocol and acceptance contracts |
| One mission class drives the headline | Report each class separately before aggregation |
| Statistical significance is mistaken for practical value | Report effect size, uncertainty, quality, and cost per success |
| Results are generalized too broadly | Enforce the public claims matrix |

---

## 15. Dependencies

Milestone 10 depends on:

- the completed Milestone 9 testing, validation, and evaluation backbone;
- the verified governed JMeter mission closure;
- pre-execution authorization;
- executed and persisted Persona Assessor verdicts;
- valid Persona Ledger chains;
- sealed mission manifests;
- stable model and provider usage telemetry;
- repeatable governed and ungoverned mission runners;
- versioned mission contracts and analysis tooling.

Selenium governance closure and additional tool integrations may strengthen the corpus, but they do not replace the requirement for token-bearing, model-mediated missions.

---

## 16. Exit Condition

Milestone 10 is complete when Persona Engineering has produced and independently reproduced a controlled governed-versus-ungoverned dataset that:

1. covers all required mission classes;
2. attributes actual or explicitly labeled estimated token usage to every mission component;
3. preserves matched conditions and mode isolation;
4. binds usage to mission outcomes and evidence;
5. quantifies savings, overhead, cost per successful mission, completion efficiency, context behavior, and uncertainty;
6. supports only evidence-bounded public claims; and
7. passes AC-10.1 through AC-10.14.

The closure decision must report the observed result even when governance yields no net token reduction.

---

## 17. Immediate Initiation Actions

1. Ratify this charter as the Milestone 10 baseline.
2. Inventory every current model call and available token-usage field in the Persona Engineering execution chain.
3. Define and validate the token telemetry schema.
4. Select and freeze one mission in each required mission class.
5. Implement the passive ungoverned observation path.
6. Validate mode isolation and mission pairing.
7. Execute the instrumentation pilot.
8. Freeze the final sample size and analysis plan.
9. Run, seal, analyze, reproduce, and report the final comparison.

---

## 18. Formal Milestone Statement

> **Milestone 10 will be achieved when Persona Engineering replaces theoretical token-efficiency claims with the first controlled, reproducible, mission-level measurement of governed versus ungoverned token consumption—while preserving mission quality, failure evidence, governance overhead, and statistical uncertainty as first-class results.**

