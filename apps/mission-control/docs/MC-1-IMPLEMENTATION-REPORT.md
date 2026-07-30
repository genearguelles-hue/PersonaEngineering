# Milestone MC-1 — Mission Control Foundation

**Status:** Implemented and verified
**Version:** 0.1.0
**Date:** 2026-07-28
**Target location:** `PersonaEngineering/apps/mission-control`

## Outcome

MC-1 establishes an executable control-plane foundation for the Persona
Engineering desktop application. It connects a first React operator screen to
a local FastAPI service and routes `pe.mission.v1` Selenium missions through a
normalized tool adapter.

The implementation deliberately keeps testing-tool logic outside the desktop
interface. The interface submits a mission contract; the controller performs
validation and governance preflight; the adapter translates the authorized
request into the existing PE CLI invocation; and the ledger records and seals
the result.

## Delivered

### Desktop and interface

- Tauri 2 desktop-shell configuration
- React and TypeScript Mission Center screen
- System and adapter health display
- Governed/ungoverned mission selection
- Test Executor persona binding
- Selenium mission configuration
- Live mission-state polling
- Lifecycle event timeline
- Result and token-telemetry summary
- Evidence-integrity summary

### PE Control API

- `GET /api/v1/health`
- `GET /api/v1/adapters`
- `GET /api/v1/adapters/{adapter_id}`
- `POST /api/v1/missions/validate`
- `POST /api/v1/missions`
- `GET /api/v1/missions/{mission_id}`
- `GET /api/v1/missions/{mission_id}/events`
- `GET /api/v1/missions/{mission_id}/evidence`
- `POST /api/v1/missions/{mission_id}/cancel`
- `WS /api/v1/ws/missions/{mission_id}`

The canonical interface description is
`contracts/pe-control-api.v1.yaml`.

### Normalized Tool Adapter Contract

The MC-1 contract defines the following lifecycle:

1. `discover`
2. `health`
3. `capabilities`
4. `configure`
5. `authorize`
6. `execute`
7. `status`
8. `cancel`
9. `collect_evidence`
10. `normalize_result`
11. `record_telemetry`

This lifecycle is transport-neutral and can be implemented by CLI, MCP, HTTP,
or hybrid adapters.

### Selenium integration

Real mode invokes:

```bash
python3 -m pe_mission run <materialized-mission.json> \
  --adapter pe-cli \
  --persona-engineering-root <configured-root>
```

Security and control properties:

- no shell invocation;
- explicit command arguments;
- explicit working directory;
- mission timeout;
- process cancellation;
- stdout and stderr capture;
- SHA-256 evidence hashes;
- normalized exit status;
- provider token telemetry extraction when supplied.

### Governance and evidence

- explicit `AUTHORIZED`, `BLOCKED`, or `BYPASSED` decision;
- persona binding required;
- adapter action allowlist;
- governed and ungoverned modes visibly distinguished;
- ordered mission events;
- SHA-256 event hash chain;
- terminal-chain verification;
- sealed artifact manifest;
- fixture evidence explicitly labeled;
- runtime verdict distinguished from a future Persona Assessor verdict.

## Verification results

| Check | Result |
| --- | --- |
| Python source compilation | PASS |
| Controller and contract tests | 8 PASS |
| FastAPI health endpoint | PASS |
| Adapter discovery | PASS |
| Governed mission lifecycle | PASS |
| Ungoverned comparison decision | PASS |
| Mission result normalization | PASS |
| Token telemetry capture | PASS |
| Ledger hash-chain verification | PASS |
| Evidence-manifest sealing | PASS |
| React TypeScript compilation | PASS |
| Vite production build | PASS |
| Live controller smoke mission | PASS |

Live smoke result:

```json
{
  "health": "healthy",
  "execution_mode": "fixture",
  "state": "completed",
  "result": "passed",
  "total_tokens": 1024,
  "events": 6,
  "ledger_valid": true,
  "artifacts": 5
}
```

The token value above is deterministic fixture telemetry and is not presented
as provider-measured production consumption.

## Integration steps on the Persona Engineering Mac

Copy the `mission-control` directory into:

```text
/Users/genea1/PersonaEngineering/apps/mission-control
```

Then:

```bash
cd /Users/genea1/PersonaEngineering/apps/mission-control
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -e 'controller[test]'
export PE_MC_EXECUTION_MODE=real
export PERSONA_ENGINEERING_ROOT=/Users/genea1/PersonaEngineering
pe-mission-control
```

In a second terminal:

```bash
cd /Users/genea1/PersonaEngineering/apps/mission-control/frontend
npm install
npm run tauri dev
```

Before running real mode, execute the existing CLI command once from the PE
repository to confirm that its module path and command flags still match:

```bash
python3 -m pe_mission run \
  examples/selenium_saucedemo_checkout_governed.json \
  --adapter pe-cli \
  --persona-engineering-root /Users/genea1/PersonaEngineering
```

## Known MC-1 boundary

- Fixture mode was fully exercised in this workspace.
- The external macOS Persona Engineering repository and live browser were not
  mounted here, so real Selenium execution must be verified after integration.
- The Tauri source and configuration are included, but the native bundle was
  not compiled because Rust was unavailable in this workspace.
- MC-1 records a deterministic runtime verdict. Persona Assessor invocation is
  intentionally reserved for a later milestone.
- The controller runs as a separate local process in MC-1. Packaging it as a
  signed Tauri sidecar belongs in the desktop-distribution milestone.

## Recommended MC-2

**MC-2: Multi-Tool Operations**

1. Integrate and verify the module inside the real Persona Engineering
   repository.
2. Execute the live governed SauceDemo Selenium mission from the desktop.
3. Add JMeter using the same adapter contract.
4. Add Playwright after its PE CLI baseline is complete.
5. Add mission history and indexed ledger search.
6. Begin matched governed-versus-ungoverned telemetry capture.
