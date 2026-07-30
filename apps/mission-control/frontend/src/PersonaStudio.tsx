import { FormEvent, useEffect, useMemo, useState } from "react";
import {
  createBehavioralIncident,
  createPersonaDeltaProposal,
  createRegressionComparison,
  listBehavioralIncidents,
  listPersonaDeltaProposals,
  listPersonaVersions,
  listRegressionComparisons,
  reviewPersonaDeltaProposal,
} from "./api";
import type {
  BehavioralIncident,
  IncidentClassification,
  PersonaDeltaProposal,
  PersonaVersion,
  RegressionComparison,
} from "./types";

interface PersonaStudioProps {
  missionId?: string;
  onError: (message: string) => void;
}

const classificationLabels: Record<IncidentClassification, string> = {
  behavioral_deviation: "Behavioral deviation",
  policy_violation: "Policy violation",
  inconsistent_output: "Inconsistent output",
  boundary_breach: "Boundary breach",
  other: "Other",
};

export default function PersonaStudio({
  missionId,
  onError,
}: PersonaStudioProps) {
  const [incidents, setIncidents] = useState<BehavioralIncident[]>([]);
  const [proposals, setProposals] = useState<PersonaDeltaProposal[]>([]);
  const [selectedProposalId, setSelectedProposalId] = useState<string>();
  const [comparisons, setComparisons] = useState<RegressionComparison[]>([]);
  const [versions, setVersions] = useState<PersonaVersion[]>([]);
  const [busy, setBusy] = useState(false);
  const [incidentForm, setIncidentForm] = useState({
    classification: "behavioral_deviation" as IncidentClassification,
    title: "",
    description: "",
  });
  const [proposalForm, setProposalForm] = useState({
    incident_id: "",
    proposed_version: "1.0.1",
    title: "",
    hypothesis: "",
    primitive_id: "",
    current_value: "",
    proposed_value: "",
    rationale: "",
  });
  const [reviewNotes, setReviewNotes] = useState(
    "Reviewed against persona invariants and regression obligations.",
  );
  const [regressionForm, setRegressionForm] = useState({
    metric: "mission_alignment",
    baseline: "0.80",
    candidate: "0.90",
    objective: "increase" as "increase" | "decrease" | "maintain",
    notes: "",
  });

  const selectedProposal = useMemo(
    () => proposals.find((item) => item.proposal_id === selectedProposalId),
    [proposals, selectedProposalId],
  );

  async function refresh() {
    const [nextIncidents, nextProposals] = await Promise.all([
      listBehavioralIncidents(),
      listPersonaDeltaProposals(),
    ]);
    setIncidents(nextIncidents);
    setProposals(nextProposals);
    setProposalForm((current) => ({
      ...current,
      incident_id: current.incident_id || nextIncidents[0]?.incident_id || "",
    }));
    setSelectedProposalId((current) => current || nextProposals[0]?.proposal_id);
  }

  useEffect(() => {
    refresh().catch((reason: Error) => onError(reason.message));
  }, []);

  useEffect(() => {
    if (!selectedProposal) {
      setComparisons([]);
      setVersions([]);
      return;
    }
    Promise.all([
      listRegressionComparisons(selectedProposal.proposal_id),
      listPersonaVersions(selectedProposal.persona_id),
    ])
      .then(([nextComparisons, nextVersions]) => {
        setComparisons(nextComparisons);
        setVersions(nextVersions);
      })
      .catch((reason: Error) => onError(reason.message));
  }, [selectedProposal?.proposal_id]);

  async function reportIncident(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    try {
      const incident = await createBehavioralIncident({
        mission_id: missionId,
        persona_id: "test-executor",
        persona_version: "1.0.0",
        classification: incidentForm.classification,
        title: incidentForm.title,
        description: incidentForm.description,
        evidence_refs: missionId ? [`mission:${missionId}`] : [],
        reported_by: "mission-control-operator",
      });
      setIncidentForm({
        classification: "behavioral_deviation",
        title: "",
        description: "",
      });
      setProposalForm((current) => ({
        ...current,
        incident_id: incident.incident_id,
      }));
      await refresh();
    } catch (reason) {
      onError(reason instanceof Error ? reason.message : "Incident creation failed.");
    } finally {
      setBusy(false);
    }
  }

  async function draftProposal(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    try {
      const proposal = await createPersonaDeltaProposal({
        incident_id: proposalForm.incident_id,
        persona_id: "test-executor",
        base_version: "1.0.0",
        proposed_version: proposalForm.proposed_version,
        title: proposalForm.title,
        hypothesis: proposalForm.hypothesis,
        primitive_changes: [
          {
            primitive_id: proposalForm.primitive_id,
            operation: "replace",
            current_value: proposalForm.current_value,
            proposed_value: proposalForm.proposed_value,
            rationale: proposalForm.rationale,
          },
        ],
        safety_constraints: [
          "Preserve all persona axioms.",
          "Do not expand tool authority.",
        ],
        regression_objectives: [
          "Improve the target behavior without reducing boundary compliance.",
        ],
        proposed_by: "mission-control-operator",
      });
      setSelectedProposalId(proposal.proposal_id);
      await refresh();
    } catch (reason) {
      onError(reason instanceof Error ? reason.message : "Proposal creation failed.");
    } finally {
      setBusy(false);
    }
  }

  async function review(decision: "approve" | "reject") {
    if (!selectedProposal) return;
    setBusy(true);
    try {
      const reviewed = await reviewPersonaDeltaProposal(
        selectedProposal.proposal_id,
        decision,
        "mission-control-reviewer",
        reviewNotes,
      );
      setProposals((current) =>
        current.map((item) =>
          item.proposal_id === reviewed.proposal_id ? reviewed : item,
        ),
      );
      setVersions(await listPersonaVersions(reviewed.persona_id));
    } catch (reason) {
      onError(reason instanceof Error ? reason.message : "Review failed.");
    } finally {
      setBusy(false);
    }
  }

  async function recordRegression(event: FormEvent) {
    event.preventDefault();
    if (!selectedProposal) return;
    const baseline = Number(regressionForm.baseline);
    const candidate = Number(regressionForm.candidate);
    const passed =
      regressionForm.objective === "increase"
        ? candidate >= baseline
        : regressionForm.objective === "decrease"
          ? candidate <= baseline
          : candidate === baseline;
    setBusy(true);
    try {
      const comparison = await createRegressionComparison(
        selectedProposal.proposal_id,
        {
          metrics: [
            {
              metric: regressionForm.metric,
              baseline,
              candidate,
              unit: "score",
              objective: regressionForm.objective,
              passed,
            },
          ],
          verdict: passed ? "pass" : "fail",
          notes: regressionForm.notes,
          recorded_by: "mission-control-operator",
        },
      );
      setComparisons((current) => [comparison, ...current]);
    } catch (reason) {
      onError(
        reason instanceof Error ? reason.message : "Regression recording failed.",
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <header className="topbar">
        <div>
          <p className="eyebrow">PERSONA GOVERNANCE / PROPOSAL-ONLY</p>
          <h1>Persona Studio</h1>
          <p>Diagnose behavior, review primitive deltas, and compare candidate versions.</p>
        </div>
        <div className="safety-badge">
          <span>NO AUTO-MUTATION</span>
          <strong>Human review required</strong>
        </div>
      </header>

      <section className="metrics-grid" aria-label="Persona governance status">
        <StudioMetric label="Behavioral incidents" value={incidents.length} />
        <StudioMetric
          label="Pending review"
          value={proposals.filter((item) => item.status === "pending_review").length}
        />
        <StudioMetric
          label="Approved candidates"
          value={proposals.filter((item) => item.status === "approved").length}
        />
        <StudioMetric
          label="Applied automatically"
          value={0}
          safe
        />
      </section>

      <section className="studio-grid">
        <section className="panel studio-panel">
          <div className="panel-heading">
            <div>
              <p className="eyebrow">BEHAVIORAL INCIDENTS</p>
              <h2>Observed persona behavior</h2>
            </div>
            <span className="contract-pill">pe.behavioral-incident.v1</span>
          </div>

          <form onSubmit={reportIncident} className="studio-form">
            <div className="field-grid">
              <label>
                Classification
                <select
                  value={incidentForm.classification}
                  onChange={(event) =>
                    setIncidentForm({
                      ...incidentForm,
                      classification: event.target.value as IncidentClassification,
                    })
                  }
                >
                  {Object.entries(classificationLabels).map(([value, label]) => (
                    <option value={value} key={value}>{label}</option>
                  ))}
                </select>
              </label>
              <label>
                Linked mission
                <input value={missionId ?? "Independent observation"} disabled />
              </label>
            </div>
            <label>
              Incident title
              <input
                value={incidentForm.title}
                onChange={(event) =>
                  setIncidentForm({ ...incidentForm, title: event.target.value })
                }
                placeholder="Describe the behavioral deviation"
                required
              />
            </label>
            <label>
              Evidence-backed description
              <textarea
                value={incidentForm.description}
                onChange={(event) =>
                  setIncidentForm({ ...incidentForm, description: event.target.value })
                }
                placeholder="What did the persona do, what was expected, and which evidence supports the diagnosis?"
                required
                minLength={10}
              />
            </label>
            <button className="secondary-button" disabled={busy}>
              Record behavioral incident
            </button>
          </form>

          <div className="record-list">
            {incidents.map((incident) => (
              <button
                key={incident.incident_id}
                className={
                  proposalForm.incident_id === incident.incident_id ? "selected" : ""
                }
                onClick={() =>
                  setProposalForm({
                    ...proposalForm,
                    incident_id: incident.incident_id,
                  })
                }
              >
                <span>{classificationLabels[incident.classification]}</span>
                <strong>{incident.title}</strong>
                <small>{incident.incident_id} · {incident.persona_id}@{incident.persona_version}</small>
              </button>
            ))}
            {!incidents.length && (
              <p className="empty-copy">
                Execution failures remain mission records. Add an incident only when
                evidence indicates genuine persona behavior requiring review.
              </p>
            )}
          </div>
        </section>

        <section className="panel studio-panel">
          <div className="panel-heading">
            <div>
              <p className="eyebrow">DELTA AUTHORING</p>
              <h2>Primitive change proposal</h2>
            </div>
            <span className="contract-pill">proposal only</span>
          </div>

          <form onSubmit={draftProposal} className="studio-form">
            <div className="field-grid">
              <label>
                Incident
                <select
                  value={proposalForm.incident_id}
                  onChange={(event) =>
                    setProposalForm({
                      ...proposalForm,
                      incident_id: event.target.value,
                    })
                  }
                  required
                >
                  <option value="">Select incident</option>
                  {incidents.map((incident) => (
                    <option key={incident.incident_id} value={incident.incident_id}>
                      {incident.title}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Candidate version
                <input
                  value={proposalForm.proposed_version}
                  onChange={(event) =>
                    setProposalForm({
                      ...proposalForm,
                      proposed_version: event.target.value,
                    })
                  }
                  pattern="[0-9]+\.[0-9]+\.[0-9]+"
                  required
                />
              </label>
            </div>
            <label>
              Proposal title
              <input
                value={proposalForm.title}
                onChange={(event) =>
                  setProposalForm({ ...proposalForm, title: event.target.value })
                }
                required
              />
            </label>
            <label>
              Behavioral hypothesis
              <textarea
                value={proposalForm.hypothesis}
                onChange={(event) =>
                  setProposalForm({ ...proposalForm, hypothesis: event.target.value })
                }
                required
                minLength={10}
              />
            </label>
            <div className="field-grid">
              <label>
                Primitive ID
                <input
                  value={proposalForm.primitive_id}
                  onChange={(event) =>
                    setProposalForm({
                      ...proposalForm,
                      primitive_id: event.target.value,
                    })
                  }
                  placeholder="execution.verify_result_contract"
                  required
                />
              </label>
              <label>
                Operation
                <input value="REPLACE" disabled />
              </label>
            </div>
            <div className="field-grid">
              <label>
                Current value
                <input
                  value={proposalForm.current_value}
                  onChange={(event) =>
                    setProposalForm({
                      ...proposalForm,
                      current_value: event.target.value,
                    })
                  }
                />
              </label>
              <label>
                Proposed value
                <input
                  value={proposalForm.proposed_value}
                  onChange={(event) =>
                    setProposalForm({
                      ...proposalForm,
                      proposed_value: event.target.value,
                    })
                  }
                />
              </label>
            </div>
            <label>
              Rationale
              <textarea
                value={proposalForm.rationale}
                onChange={(event) =>
                  setProposalForm({ ...proposalForm, rationale: event.target.value })
                }
                required
                minLength={5}
              />
            </label>
            <button
              className="secondary-button"
              disabled={busy || !incidents.length}
            >
              Submit for review
            </button>
          </form>
        </section>
      </section>

      <section className="panel review-workbench">
        <div className="panel-heading">
          <div>
            <p className="eyebrow">REVIEW WORKBENCH</p>
            <h2>Approval, version lineage, and regression evidence</h2>
          </div>
          <select
            className="proposal-select"
            value={selectedProposalId ?? ""}
            onChange={(event) => setSelectedProposalId(event.target.value)}
          >
            <option value="">Select proposal</option>
            {proposals.map((proposal) => (
              <option value={proposal.proposal_id} key={proposal.proposal_id}>
                {proposal.title} · {proposal.status}
              </option>
            ))}
          </select>
        </div>

        {!selectedProposal ? (
          <p className="empty-copy">Create a proposal to open the review workbench.</p>
        ) : (
          <div className="review-grid">
            <div className="proposal-detail">
              <div className="proposal-status-row">
                <span className={`state-badge ${selectedProposal.status}`}>
                  {selectedProposal.status}
                </span>
                <span className="no-apply">APPLICATION: NOT APPLIED</span>
              </div>
              <h3>{selectedProposal.title}</h3>
              <p>{selectedProposal.hypothesis}</p>
              {selectedProposal.primitive_changes.map((change) => (
                <div className="primitive-diff" key={change.primitive_id}>
                  <code>{change.primitive_id}</code>
                  <div><span>−</span>{String(change.current_value ?? "∅")}</div>
                  <div><span>+</span>{String(change.proposed_value ?? "∅")}</div>
                  <small>{change.rationale}</small>
                </div>
              ))}
              <label>
                Review notes
                <textarea
                  value={reviewNotes}
                  onChange={(event) => setReviewNotes(event.target.value)}
                  disabled={selectedProposal.status !== "pending_review"}
                />
              </label>
              <div className="review-actions">
                <button
                  className="approve-button"
                  onClick={() => review("approve")}
                  disabled={busy || selectedProposal.status !== "pending_review"}
                >
                  Approve candidate
                </button>
                <button
                  className="reject-button"
                  onClick={() => review("reject")}
                  disabled={busy || selectedProposal.status !== "pending_review"}
                >
                  Reject proposal
                </button>
              </div>
              <p className="governance-note">
                Approval does not activate or mutate the persona. Application requires a
                separate future governed deployment capability.
              </p>
            </div>

            <div>
              <h3 className="subsection-title">Version lineage</h3>
              <div className="version-lineage">
                {versions.map((version) => (
                  <div key={version.version}>
                    <span className={version.applied ? "active-node" : "candidate-node"} />
                    <strong>{version.persona_id}@{version.version}</strong>
                    <small>{version.lifecycle.replaceAll("_", " ")}</small>
                  </div>
                ))}
              </div>

              <h3 className="subsection-title">Regression comparison</h3>
              <form onSubmit={recordRegression} className="regression-form">
                <input
                  value={regressionForm.metric}
                  onChange={(event) =>
                    setRegressionForm({
                      ...regressionForm,
                      metric: event.target.value,
                    })
                  }
                  aria-label="Metric"
                  required
                />
                <input
                  type="number"
                  step="0.01"
                  value={regressionForm.baseline}
                  onChange={(event) =>
                    setRegressionForm({
                      ...regressionForm,
                      baseline: event.target.value,
                    })
                  }
                  aria-label="Baseline"
                  required
                />
                <input
                  type="number"
                  step="0.01"
                  value={regressionForm.candidate}
                  onChange={(event) =>
                    setRegressionForm({
                      ...regressionForm,
                      candidate: event.target.value,
                    })
                  }
                  aria-label="Candidate"
                  required
                />
                <select
                  value={regressionForm.objective}
                  onChange={(event) =>
                    setRegressionForm({
                      ...regressionForm,
                      objective: event.target.value as
                        | "increase"
                        | "decrease"
                        | "maintain",
                    })
                  }
                  aria-label="Objective"
                >
                  <option value="increase">Increase</option>
                  <option value="decrease">Decrease</option>
                  <option value="maintain">Maintain</option>
                </select>
                <button className="secondary-button" disabled={busy}>
                  Record comparison
                </button>
              </form>
              <div className="comparison-list">
                {comparisons.map((comparison) => (
                  <div key={comparison.comparison_id}>
                    <span className={`comparison-verdict ${comparison.verdict}`}>
                      {comparison.verdict}
                    </span>
                    {comparison.metrics.map((metric) => (
                      <p key={metric.metric}>
                        <strong>{metric.metric}</strong>
                        {metric.baseline} → {metric.candidate} {metric.unit}
                      </p>
                    ))}
                  </div>
                ))}
                {!comparisons.length && (
                  <p className="empty-copy">No regression evidence recorded yet.</p>
                )}
              </div>
            </div>
          </div>
        )}
      </section>
    </>
  );
}

function StudioMetric({
  label,
  value,
  safe,
}: {
  label: string;
  value: number;
  safe?: boolean;
}) {
  return (
    <article className="metric">
      <span>{label}</span>
      <strong className={safe ? "safe-value" : ""}>{value}</strong>
      <small>{safe ? "Safety invariant" : "Persona Studio records"}</small>
    </article>
  );
}
