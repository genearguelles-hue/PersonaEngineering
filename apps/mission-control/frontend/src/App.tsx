import { FormEvent, useEffect, useMemo, useState } from "react";
import {
  createMission,
  getEvidence,
  getHealth,
  getMission,
  getMissionEvents,
} from "./api";
import type {
  EvidenceManifest,
  MissionEvent,
  MissionForm,
  MissionRecord,
  SystemHealth,
} from "./types";
import PersonaStudio from "./PersonaStudio";

const initialForm: MissionForm = {
  name: "SauceDemo governed checkout smoke",
  governance_mode: "governed",
  scenario: "saucedemo_checkout",
  target_url: "https://www.saucedemo.com/",
  browser: "chrome",
  headless: true,
  timeout_seconds: 120,
};

const terminalStates = new Set(["completed", "failed", "cancelled"]);

function formatNumber(value?: number | null): string {
  return value == null ? "—" : value.toLocaleString();
}

function shortHash(value?: string): string {
  return value ? `${value.slice(0, 10)}…${value.slice(-6)}` : "Pending";
}

function App() {
  const [activePage, setActivePage] = useState<"mission" | "persona">("mission");
  const [health, setHealth] = useState<SystemHealth | null>(null);
  const [form, setForm] = useState<MissionForm>(initialForm);
  const [mission, setMission] = useState<MissionRecord | null>(null);
  const [events, setEvents] = useState<MissionEvent[]>([]);
  const [manifest, setManifest] = useState<EvidenceManifest | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getHealth()
      .then(setHealth)
      .catch((reason: Error) => setError(`Control API unavailable: ${reason.message}`));
  }, []);

  useEffect(() => {
    if (!mission || terminalStates.has(mission.state)) {
      return;
    }
    const timer = window.setInterval(async () => {
      try {
        const [record, nextEvents] = await Promise.all([
          getMission(mission.mission_id),
          getMissionEvents(mission.mission_id),
        ]);
        setMission(record);
        setEvents(nextEvents);
        if (terminalStates.has(record.state)) {
          const evidence = await getEvidence(record.mission_id);
          setManifest(evidence);
        }
      } catch (reason) {
        setError(reason instanceof Error ? reason.message : "Mission refresh failed.");
      }
    }, 450);
    return () => window.clearInterval(timer);
  }, [mission?.mission_id, mission?.state]);

  const elapsed = useMemo(() => {
    if (!mission?.result) return "—";
    return `${(mission.result.duration_ms / 1000).toFixed(2)}s`;
  }, [mission]);

  async function launch(event: FormEvent) {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    setEvents([]);
    setManifest(null);
    try {
      const record = await createMission(form);
      setMission(record);
      setEvents(await getMissionEvents(record.mission_id));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Mission launch failed.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark">Π</div>
          <div>
            <span className="brand-kicker">PERSONA ENGINEERING</span>
            <strong>Mission Control</strong>
          </div>
        </div>

        <nav aria-label="Mission Control areas">
          <button
            className={`nav-item ${activePage === "mission" ? "active" : ""}`}
            onClick={() => setActivePage("mission")}
          ><span>⌁</span>Mission Center</button>
          <button className="nav-item" disabled><span>◈</span>Operations</button>
          <button className="nav-item" disabled><span>⌘</span>Tool Control</button>
          <button className="nav-item" disabled><span>◫</span>Token Economics</button>
          <button
            className={`nav-item ${activePage === "persona" ? "active" : ""}`}
            onClick={() => setActivePage("persona")}
          ><span>◎</span>Persona Studio</button>
          <button className="nav-item" disabled><span>◇</span>Governance</button>
          <button className="nav-item" disabled><span>▤</span>Ledger & Evidence</button>
        </nav>

        <div className="system-card">
          <div className="system-row">
            <span className={`status-dot ${health?.status ?? "offline"}`} />
            <div>
              <strong>{health ? "Control plane online" : "Connecting…"}</strong>
              <span>API v{health?.version ?? "—"}</span>
            </div>
          </div>
          <div className="system-meta">
            <span>EXECUTION</span>
            <strong>{health?.execution_mode?.toUpperCase() ?? "UNKNOWN"}</strong>
          </div>
        </div>
      </aside>

      <main>
        {error && (
          <div className="error-banner" role="alert">
            <strong>Mission Control notice</strong>
            <span>{error}</span>
            <button onClick={() => setError(null)}>Dismiss</button>
          </div>
        )}

        {activePage === "mission" ? (
          <>
        <header className="topbar">
          <div>
            <p className="eyebrow">CONTROL SURFACE / MC-1</p>
            <h1>Mission Center</h1>
            <p>Authorize, execute, and inspect Persona Engineering missions.</p>
          </div>
          <div className="topbar-badge">
            <span className={`status-dot ${health?.adapters[0]?.status ?? "offline"}`} />
            Selenium PE CLI
            <small>{health?.adapters[0]?.execution_mode ?? "offline"}</small>
          </div>
        </header>

        <section className="metrics-grid" aria-label="Mission status">
          <Metric label="Mission state" value={mission?.state ?? "Ready"} tone={mission?.state} />
          <Metric
            label="Governance"
            value={mission?.authorization?.decision ?? form.governance_mode}
            caption={mission?.authorization?.policy_bindings.length ? `${mission.authorization.policy_bindings.length} policies` : "Preflight pending"}
          />
          <Metric label="Duration" value={elapsed} caption="Adapter execution" />
          <Metric
            label="Token burn"
            value={formatNumber(mission?.result?.telemetry.total_tokens)}
            caption={mission?.result?.telemetry.provider_reported ? "Provider reported" : mission?.result ? "Fixture / estimated" : "Awaiting telemetry"}
          />
        </section>

        <section className="workspace-grid">
          <form className="panel mission-form" onSubmit={launch}>
            <div className="panel-heading">
              <div>
                <p className="eyebrow">NEW MISSION</p>
                <h2>Selenium web test</h2>
              </div>
              <span className="contract-pill">pe.mc.launch.v1</span>
            </div>

            <label>
              Mission name
              <input
                value={form.name}
                onChange={(event) => setForm({ ...form, name: event.target.value })}
                required
                minLength={3}
              />
            </label>

            <div className="field-grid">
              <label>
                Scenario
                <select
                  value={form.scenario}
                  onChange={(event) => setForm({ ...form, scenario: event.target.value })}
                >
                  <option value="saucedemo_checkout">SauceDemo checkout</option>
                </select>
              </label>
              <label>
                Browser
                <select
                  value={form.browser}
                  onChange={(event) => setForm({ ...form, browser: event.target.value })}
                >
                  <option value="chrome">Chrome</option>
                </select>
              </label>
            </div>

            <label>
              Target URL
              <input
                type="url"
                value={form.target_url}
                onChange={(event) => setForm({ ...form, target_url: event.target.value })}
                required
              />
            </label>

            <div className="mode-selector" role="group" aria-label="Governance mode">
              <button
                type="button"
                className={form.governance_mode === "governed" ? "selected" : ""}
                onClick={() => setForm({ ...form, governance_mode: "governed" })}
              >
                <span className="mode-icon">◇</span>
                <span><strong>Governed</strong><small>Authorize before execution</small></span>
              </button>
              <button
                type="button"
                className={form.governance_mode === "ungoverned" ? "selected warning" : ""}
                onClick={() => setForm({ ...form, governance_mode: "ungoverned" })}
              >
                <span className="mode-icon">○</span>
                <span><strong>Ungoverned</strong><small>Comparison baseline</small></span>
              </button>
            </div>

            <div className="field-grid compact">
              <label>
                Timeout
                <div className="input-suffix">
                  <input
                    type="number"
                    min={1}
                    max={3600}
                    value={form.timeout_seconds}
                    onChange={(event) => setForm({ ...form, timeout_seconds: Number(event.target.value) })}
                  />
                  <span>sec</span>
                </div>
              </label>
              <label className="checkbox-label">
                Browser mode
                <button
                  type="button"
                  className={`toggle ${form.headless ? "on" : ""}`}
                  onClick={() => setForm({ ...form, headless: !form.headless })}
                  aria-pressed={form.headless}
                >
                  <span />
                  {form.headless ? "Headless" : "Visible"}
                </button>
              </label>
            </div>

            <div className="persona-binding">
              <span>BOUND PERSONA</span>
              <strong>Test Executor</strong>
              <small>test-executor@1.0.0</small>
            </div>

            <button className="launch-button" type="submit" disabled={submitting || !health}>
              {submitting ? "Submitting mission…" : "Authorize & launch mission"}
              <span>→</span>
            </button>
          </form>

          <section className="panel execution-panel">
            <div className="panel-heading">
              <div>
                <p className="eyebrow">LIVE EXECUTION</p>
                <h2>{mission ? mission.mission_id : "No active mission"}</h2>
              </div>
              <StateBadge state={mission?.state} />
            </div>

            {!mission ? (
              <div className="empty-state">
                <div className="radar">
                  <span />
                  <span />
                  <span />
                  <i />
                </div>
                <strong>Control plane standing by</strong>
                <p>Configure a mission to begin governed execution.</p>
              </div>
            ) : (
              <>
                <div className="execution-summary">
                  <div>
                    <span>ADAPTER</span>
                    <strong>{mission.adapter_id}</strong>
                  </div>
                  <div>
                    <span>MODE</span>
                    <strong>{mission.governance_mode}</strong>
                  </div>
                  <div>
                    <span>RESULT</span>
                    <strong>{mission.result?.status ?? "pending"}</strong>
                  </div>
                </div>

                <div className="timeline">
                  {events.map((item) => (
                    <div className="timeline-item" key={item.sequence}>
                      <div className="timeline-marker">{item.sequence}</div>
                      <div>
                        <strong>{item.event_type.replaceAll("_", " ")}</strong>
                        <span>{new Date(item.timestamp).toLocaleTimeString()}</span>
                        <small>{shortHash(item.event_hash)}</small>
                      </div>
                    </div>
                  ))}
                  {!events.length && <p className="muted">Waiting for lifecycle events…</p>}
                </div>

                {mission.result && (
                  <div className={`result-card ${mission.result.status}`}>
                    <div>
                      <span>RUNTIME VERDICT</span>
                      <strong>{mission.result.status === "passed" ? "PASS" : "FAIL"}</strong>
                    </div>
                    <p>{mission.result.summary}</p>
                    {mission.result.fixture && <em>Fixture evidence — no browser launched</em>}
                  </div>
                )}
              </>
            )}
          </section>
        </section>

        <section className="panel evidence-strip">
          <div>
            <p className="eyebrow">EVIDENCE INTEGRITY</p>
            <h2>{manifest?.ledger.valid ? "Hash chain verified" : "Awaiting mission seal"}</h2>
          </div>
          <EvidenceStat label="Ledger events" value={manifest?.ledger.event_count?.toString() ?? "—"} />
          <EvidenceStat label="Artifacts sealed" value={manifest?.artifacts.length.toString() ?? "—"} />
          <EvidenceStat label="Terminal hash" value={shortHash(manifest?.ledger.terminal_hash)} mono />
          <EvidenceStat label="Manifest hash" value={shortHash(manifest?.manifest_hash)} mono />
        </section>
          </>
        ) : (
          <PersonaStudio
            missionId={mission?.mission_id}
            onError={(message) => setError(message)}
          />
        )}
      </main>
    </div>
  );
}

function Metric({
  label,
  value,
  caption,
  tone,
}: {
  label: string;
  value: string;
  caption?: string;
  tone?: string;
}) {
  return (
    <article className="metric">
      <span>{label}</span>
      <strong className={tone ? `tone-${tone}` : ""}>{value}</strong>
      <small>{caption ?? "Current mission"}</small>
    </article>
  );
}

function StateBadge({ state }: { state?: string }) {
  return <span className={`state-badge ${state ?? "ready"}`}>{state ?? "ready"}</span>;
}

function EvidenceStat({
  label,
  value,
  mono,
}: {
  label: string;
  value: string;
  mono?: boolean;
}) {
  return (
    <div className="evidence-stat">
      <span>{label}</span>
      <strong className={mono ? "mono" : ""}>{value}</strong>
    </div>
  );
}

export default App;
