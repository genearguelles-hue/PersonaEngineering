# Persona Engineering Mission Control

Milestone **MC-1: Mission Control Foundation** establishes the first executable
desktop control plane for the Persona Engineering domain layer.

Version **0.2.1 (MC-1.1.1)** repairs the Selenium result vocabulary mismatch and
adds the first proposal-only Persona Studio governance workflow.

The milestone includes:

- a Tauri 2 desktop shell;
- a React and TypeScript operator interface;
- a FastAPI-based PE Control API;
- a normalized Tool Adapter Contract;
- a Selenium adapter for the existing `pe.mission.v1` runner;
- mission lifecycle events, hash-chained evidence, and result normalization;
- a normalized Selenium result contract for `pe.test-run.envelope.v1`;
- behavioral incidents kept distinct from execution failures;
- reviewable, versioned persona-delta proposals with no automatic mutation;
- regression comparisons and a hash-chained persona-governance audit trail;
- a deterministic fixture mode for development without a browser or PE runtime.

## Architecture

```text
React operator interface
        |
        | HTTP / WebSocket
        v
PE Control API (FastAPI)
        |
        +-- Mission service
        +-- Governance preflight
        +-- Tool adapter registry
        +-- Evidence ledger
                 |
                 v
      Selenium PE CLI adapter
                 |
                 v
python3 -m pe_mission run <mission.json>
  --adapter pe-cli
  --persona-engineering-root <root>
```

Mission Control does not embed testing-tool logic in the UI. Every tool is
exposed through the normalized adapter lifecycle defined in
`contracts/tool-adapter.v1.schema.json`.

The desktop submits the operator-oriented
`pe.mission-control.launch.v1` request. Before real execution, the controller
translates it into the strict canonical `pe.mission.v1` envelope, persists both
representations, and asks the authoritative runtime to validate the canonical
document.

## Project layout

```text
mission-control/
├── contracts/                 JSON Schema and OpenAPI contracts
├── controller/                Python control service
│   └── pe_mission_control/
├── desktop/src-tauri/         Tauri desktop shell
├── examples/                  Example `pe.mission.v1` envelopes
├── frontend/                  React operator interface
├── patches/                   Reviewed compatibility patches for PE runtime
└── tests/                     Controller unit tests
```

## Quick start

### 1. Start the control API

```bash
cd apps/mission-control
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -e controller
pe-mission-control
```

The API listens on `http://127.0.0.1:8765`. Interactive API documentation is
available at `http://127.0.0.1:8765/docs`.

### 2. Start the interface

```bash
cd apps/mission-control/frontend
npm install
npm run dev
```

Open `http://localhost:1420`.

### 3. Start the desktop shell

Rust and the platform-specific Tauri prerequisites are required.

```bash
cd apps/mission-control/frontend
npm run tauri dev
```

## Execution modes

Fixture mode is the safe default:

```bash
export PE_MC_EXECUTION_MODE=fixture
```

It exercises the complete control, governance, event, evidence, and UI path
without claiming that a browser was launched.

To invoke the existing Persona Engineering CLI:

```bash
export PE_MC_EXECUTION_MODE=real
export PERSONA_ENGINEERING_ROOT=/Users/genea1/PersonaEngineering
export PE_GOV="/Users/genea1/Documents/Literature & Content Projects/White Paper Projects/Persona Engineering/pe-mission-control"
export PYTHONPATH="$PE_GOV"
export PE_MC_PYTHON=/usr/local/bin/python3
```

The Selenium adapter executes:

```bash
python3 -m pe_mission run <materialized-mission.json> \
  --adapter pe-cli \
  --persona-engineering-root "$PERSONA_ENGINEERING_ROOT"
```

No shell is used. Arguments are passed directly to the subprocess.

Real-mode health is `healthy` only when the PE root exists and the configured
Python interpreter can import `pe_mission`. The adapter also executes
`pe_mission validate` against the materialized canonical envelope before
starting Selenium.

### Required Selenium assessor compatibility patch

The authoritative Selenium envelope reports `tests`, `failures`, `errors`,
`skipped`, and per-test durations. Its original assessor expected `passed`,
`failed`, and `duration_seconds`, which converted a successful two-test run
into `0/0/0`.

Apply the bundled compatibility patch once to the governance runtime:

```bash
cd "$PE_GOV"
git apply --check \
  /Users/genea1/PersonaEngineering/apps/mission-control/patches/pe_mission_selenium_result_contract.patch
git apply \
  /Users/genea1/PersonaEngineering/apps/mission-control/patches/pe_mission_selenium_result_contract.patch

PYTHONPATH="$PE_GOV" /usr/local/bin/python3 \
  /Users/genea1/PersonaEngineering/apps/mission-control/scripts/verify_selenium_result_contract.py
```

The patch derives:

```text
passed = tests - failures - errors - skipped
failed = failures + errors
duration_seconds = sum(testcases[*].time_seconds)
```

Mission Control independently writes `selenium-result-contract.json` for each
real mission. It does not silently override a conflicting authoritative
verdict.

## API summary

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/api/v1/health` | Controller and adapter health |
| `GET` | `/api/v1/adapters` | Discover registered adapters |
| `POST` | `/api/v1/missions/validate` | Validate a mission envelope |
| `POST` | `/api/v1/missions` | Authorize and start a mission |
| `GET` | `/api/v1/missions/{mission_id}` | Retrieve mission state |
| `GET` | `/api/v1/missions/{mission_id}/events` | Retrieve lifecycle events |
| `GET` | `/api/v1/missions/{mission_id}/evidence` | Retrieve evidence manifest |
| `POST` | `/api/v1/missions/{mission_id}/cancel` | Request cancellation |
| `WS` | `/api/v1/ws/missions/{mission_id}` | Stream mission state |
| `POST` | `/api/v1/behavioral-incidents` | Record an evidence-backed behavioral incident |
| `GET` | `/api/v1/behavioral-incidents` | List behavioral incidents |
| `POST` | `/api/v1/persona-delta-proposals` | Create a proposal-only primitive delta |
| `POST` | `/api/v1/persona-delta-proposals/{proposal_id}/review` | Approve or reject a candidate |
| `POST` | `/api/v1/persona-delta-proposals/{proposal_id}/regression-comparisons` | Record baseline/candidate evidence |
| `GET` | `/api/v1/personas/{persona_id}/versions` | View baseline and candidate versions |
| `GET` | `/api/v1/persona-governance/integrity` | Verify the governance audit chain |

The canonical API definition is `contracts/pe-control-api.v1.yaml`.

Approval is intentionally not application. The API contains no endpoint that
modifies or activates a persona; every approved candidate remains
`application_status: not_applied`.

## Integration note

This module is intended to be copied to:

```text
/Users/genea1/PersonaEngineering/apps/mission-control
```

The existing PE repository is not included in this standalone milestone
artifact. Real execution therefore requires configuring
`PERSONA_ENGINEERING_ROOT`.
