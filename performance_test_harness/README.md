# Persona Engineering Performance Test Harness

This package orders policy-constrained JMeter runs through the Selenium/JMeter
MCP server and records the orchestration trajectory in the Persona Ledger.

For a normal run, the coordinator appends exactly three events to
`persona_ledger/performance_run_events.jsonl`:

1. `performance.run.requested`
2. `performance.run.started`
3. One terminal event: `completed`, `failed`, `timed_out`, or `error`

Every event carries the run ID, correlation ID, plan, contract versions,
timestamps, status, and only the **names** of supplied JMeter properties. The
terminal completed event embeds the executor-generated `pe.jmeter.evidence.v1`
manifest with artifact byte counts and SHA-256 digests. Property values are
never written to the Ledger.

Events validate against `schemas/performance_run_event.schema.json`. The writer
adds a SHA-256 event hash and previous-event hash before an append, then flushes
and synchronizes the JSONL file.

## Run through MCP

Install the schema-validation dependency once:

```bash
python3 -m pip install -r performance_test_harness/requirements.txt
```

With the JMeter MCP server available at `http://127.0.0.1:8000/mcp/`:

```bash
python3 -m performance_test_harness run \
  --plan httpbin_smoke.jmx \
  --run-id ca110003 \
  --property smoke_host=127.0.0.1 \
  --property smoke_port=18080 \
  --property smoke_protocol=http \
  --property smoke_path=/get
```

Set `JMETER_MCP_URL` or pass `--mcp-url` for another deployment.

## Verify the Ledger

```bash
python3 -m performance_test_harness verify-ledger
```

An `{"ok": true}` result proves that every event validates and the append-only
hash chain is intact. It does not independently re-fetch or re-hash remote
artifacts; those hashes originate inside the isolated JMeter executor and cross
the trusted evidence-manifest contract.
