#!/bin/bash

BASE_URL="${1:-http://localhost:8000}"
API_KEY="${PERSONA_API_KEY:-dev-local-key}"

echo "Testing: $BASE_URL/personas"

curl -i "$BASE_URL/personas" \
  -H "x-api-key: $API_KEY"