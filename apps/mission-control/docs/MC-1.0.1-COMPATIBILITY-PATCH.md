# MC-1.0.1 — Canonical Mission Compatibility Patch

**Date:** 2026-07-28
**Scope:** Mission Control launch request → authoritative `pe.mission.v1`

## Reason for the patch

MC-1.0.0 passed its internal fixture workflow but sent its operator-oriented
request directly to the external `pe_mission` runtime. The authoritative
runtime rejected that document because its canonical schema requires fields
such as `requested_at`, `requested_by`, `persona_bindings`, `tool_request`,
`governance`, `evidence_requirements`, and `acceptance_criteria`.

MC-1.0.1 establishes an explicit compatibility boundary:

```text
Desktop form
  → pe.mission-control.launch.v1
  → canonical translator
  → pe.mission.v1
  → authoritative runtime validation
  → Selenium execution
```

## Corrective changes

- Introduced the distinct `pe.mission-control.launch.v1` operator contract.
- Added deterministic translation to canonical `pe.mission.v1`.
- Changed generated mission IDs from `mc-*` to schema-valid `pe-mc-*`.
- Added planner, executor, and assessor persona bindings.
- Added canonical Selenium capability and parameter mapping.
- Added governance, constraints, evidence, acceptance, and label structures.
- Persisted the original request as `operator-request.json`.
- Persisted the runtime envelope as `mission.json`.
- Added `pe_mission validate` before every real execution.
- Strengthened adapter health to test whether the configured Python
  interpreter can import `pe_mission`.
- Added module path and probe error information to adapter health.
- Explicitly block live ungoverned execution because the current canonical
  schema permits only `"mode": "governed"`.
- Retained ungoverned fixture mode for interface and comparison-path testing.

## Canonical mapping

| Mission Control field | Canonical field |
| --- | --- |
| Mission name | `purpose` |
| Generated ID | `mission_id` |
| Current UTC time | `requested_at` |
| Dashboard operator | `requested_by` |
| Test Executor | `persona_bindings.executor` |
| Scenario | `tool_request.parameters.suite_id` |
| Target URL | `tool_request.parameters.base_url` |
| Browser | `tool_request.parameters.browser` |
| Headless | `tool_request.parameters.headless` |
| Timeout | `constraints.timeout_seconds` |
| Governed selection | `governance.mode` |

## Verification

- Controller and API tests: **8 passed**
- Canonical translation assertions: **passed**
- Frontend TypeScript compilation: **passed**
- Vite production build: **passed**

The external runtime remains the final authority: real execution is prevented
unless its own `validate` command returns `"decision": "valid"`.

## Apply on the Persona Engineering Mac

Stop the Uvicorn controller and Vite frontend once, then extract the patch over
the existing application from the Persona Engineering repository root:

```bash
cd /Users/genea1/PersonaEngineering

unzip -o "$HOME/Downloads/Persona_Engineering_Mission_Control_MC1.0.1.zip" \
  -d apps
```

Refresh the editable controller installation and validate:

```bash
cd /Users/genea1/PersonaEngineering/apps/mission-control

source .venv/bin/activate
python3 -m pip install -e 'controller[test]'
python3 -m pytest -q
```

Refresh and start the frontend:

```bash
cd /Users/genea1/PersonaEngineering/apps/mission-control/frontend
npm install
npm run dev
```

Start the real controller in another terminal:

```bash
cd /Users/genea1/PersonaEngineering/apps/mission-control
source .venv/bin/activate

export PE_GOV="/Users/genea1/Documents/Literature & Content Projects/White Paper Projects/Persona Engineering/pe-mission-control"
export PYTHONPATH="$PE_GOV"
export PE_MC_EXECUTION_MODE=real
export PERSONA_ENGINEERING_ROOT=/Users/genea1/PersonaEngineering
export PE_MC_PYTHON=/usr/local/bin/python3

pe-mission-control
```

The health response must show:

```json
{
  "status": "healthy",
  "execution_mode": "real",
  "details": {
    "root_exists": true,
    "module_available": true
  }
}
```
