#!/bin/bash

cd /Users/genea1/PersonaEngineering || exit 1

export PERSONA_API_KEY=dev-local-key

python3 -m uvicorn persona_backend.main:app --reload --port 8000