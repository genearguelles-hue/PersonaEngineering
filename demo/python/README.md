# Assessor and Ledger Demo

This directory contains a working demonstration of **Persona Engineering runtime tooling**, including:

- A **persona assessor** (`assessor.py`)
- A **ledger system** for tracking persona state evolution
- Test scenarios and example ledger states

These components illustrate how persona behavior can be evaluated over time against structured constraints.

---

## Overview

The assessor evaluates **persona trajectories** using ledger data that represents:

- historical interaction states
- dependency structures
- stability or degradation patterns

The goal is to provide a **diagnostic layer** that detects:
- stability vs. drift
- improving vs. worsening trajectories
- structural issues in persona evolution

---

## Key Components

### Assessor

Located in: codebase/assessor.py
The assessor:
- ingests ledger data
- evaluates trajectories
- produces structured assessments of persona state evolution

It operates on **ledger inputs**, not raw prompts, making it suitable for:
- longitudinal evaluation
- simulation environments
- governance and validation workflows

---

### Ledger System

Core files:
codebase/ledger.py
codebase/ledger_store.py
demo/python/ledger_entry.py

The ledger system represents persona state as structured records:

- entries → individual state updates
- ledgers → sequences of entries over time
- dependencies → relationships between states

This allows:
- replayable persona histories
- consistent evaluation inputs
- structured testing scenarios

---

## Running the Assessor

From the repository root:

```bash
cd demo/python
python run_assessor.py

If using a virtual environment:
source ../../venv/bin/activate
python run_assessor.py

This script:
	•	loads a sample ledger
	•	runs the assessor
	•	outputs evaluation results to the console

⸻

Running Tests

To run the test suite:
cd demo/python
python test_assessor_v2.py

This will:
	•	execute multiple test scenarios
	•	validate assessor behavior across different ledger conditions
	•	demonstrate expected outputs for stable and unstable trajectories

⸻

Ledger JSON Files

This directory includes several example ledgers:

stable_ledger.json

Represents a stable persona trajectory:
	•	consistent behavior
	•	no drift
	•	satisfies constraints over time

⸻

worsening_ledger.json

Represents a degrading trajectory:
	•	increasing instability
	•	violation of expected patterns
	•	signals potential persona drift

⸻

persona_ledger.json

A general-purpose persona history:
	•	used for baseline evaluation
	•	may include mixed or evolving behavior

⸻

dependency_ledger.json

Demonstrates interdependent state transitions:
	•	relationships between entries
	•	more complex evaluation scenarios
	•	useful for testing structural reasoning in the assessor

⸻

Conceptual Model

This demo implements a key idea from Persona Engineering:

Persona behavior should be evaluated as a trajectory over time, not as isolated responses.

The ledger + assessor system enables:
	•	stateful evaluation
	•	drift detection
	•	constraint validation
	•	structured testing of persona evolution

⸻

Suggested Workflow
	1.	Modify or create a ledger JSON file
	2.	Run run_assessor.py to evaluate it
	3.	Use test_assessor_v2.py to validate expected behavior
	4.	Iterate on persona design or constraints

⸻

Notes
	•	The system is framework-level, not production-hardened
	•	Designed for experimentation and conceptual validation
	•	Assumes familiarity with Persona Engineering concepts

⸻

Future Extensions

Potential directions:
	•	richer constraint definitions
	•	integration with live AI systems
	•	visualization of persona trajectories
	•	automated drift detection thresholds

  ---

If you want, I can also add a **tight 3–4 line pointer snippet** for your root README so users actually discover this file.
