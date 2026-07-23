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
terminal completed event embeds:

- the executor-generated `pe.jmeter.evidence.v1` manifest;
- the machine-readable `pe.jmeter.metrics.v1` summary;
- a deterministic `pe.performance.assessment.v1` verdict.

The coordinator verifies that the metrics and evidence manifest name the same
run and that their JTL SHA-256 digests match before assessment. Property values
are never written to the Ledger.

Events validate against `schemas/performance_run_event.schema.json`. The writer
adds a SHA-256 event hash and previous-event hash before an append, then flushes
and synchronizes the JSONL file. A successful terminal append also produces
`pe.performance.report.v1` JSON and Markdown projections under
`reports/performance/`.

Historical `pe.performance.run.event.v1` entries remain valid. Assessed runs use
the backward-compatible `pe.performance.run.event.v2` contract in
`schemas/performance_run_event_v2.schema.json`, allowing both versions to share
one append-only hash chain.

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

## Assessment policy

The default `pe.jmeter.smoke.baseline` policy is intentionally a smoke-test
baseline, not a production service-level objective:

- at least 1 sample;
- error rate no greater than 0;
- p95 elapsed time no greater than 1000 ms;
- throughput of at least 0.1 samples/second.

Override the thresholds explicitly when assessing a real workload:

```bash
python3 -m performance_test_harness run \
  --plan service_load.jmx \
  --max-error-rate 0.01 \
  --max-p95-elapsed-ms 500 \
  --min-throughput-per-second 20 \
  --min-sample-count 100
```

Execution completion and performance acceptance are deliberately separate.
`ok: true` means JMeter completed and trusted evidence was recorded;
`performance_accepted: true` means the policy verdict was `pass`. The other
verdicts are `fail` and `insufficient_evidence`.

## Verify the Ledger

```bash
python3 -m performance_test_harness verify-ledger
```

An `{"ok": true}` result proves that every event validates and the append-only
hash chain is intact. It does not independently re-fetch or re-hash remote
artifacts; those hashes originate inside the isolated JMeter executor and cross
the trusted evidence-manifest contract.

## Regenerate a report

Reports can be reconstructed from the verified Ledger without rerunning JMeter:

```bash
python3 -m performance_test_harness report --run-id ca110004
```

The JSON report is machine-readable. The Markdown report includes lifecycle,
metrics, policy checks, verdict, artifact hashes, and the terminal Ledger event
hash. Reports are derivative projections; the append-only Ledger remains the
source of record. Historical v1 runs can also be reported, but naturally show
no metrics or assessment because those contracts did not yet exist.
