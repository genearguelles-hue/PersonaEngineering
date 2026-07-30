# MC-1.1.1 — Frontend Null-Telemetry Guard

The real PE runtime correctly reports unavailable token telemetry as JSON
`null`. The MC-1.1 interface treated only omitted (`undefined`) values as
unavailable and called `toLocaleString()` on `null`, causing React to unmount
the interface.

MC-1.1.1:

- treats both `null` and `undefined` telemetry as unavailable;
- displays the existing em dash placeholder;
- aligns the TypeScript contract with the API's nullable telemetry fields;
- adds a React error boundary so a future rendering defect produces a visible
  recovery screen instead of an entirely black page.
