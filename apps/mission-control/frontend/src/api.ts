import type {
  BehavioralIncident,
  EvidenceManifest,
  IncidentClassification,
  MissionEvent,
  MissionForm,
  MissionRecord,
  PersonaDeltaProposal,
  PersonaVersion,
  PrimitiveChange,
  RegressionComparison,
  RegressionMetric,
  SystemHealth,
} from "./types";

const API_BASE = import.meta.env.VITE_PE_API_URL ?? "http://127.0.0.1:8765";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...init?.headers,
    },
  });
  if (!response.ok) {
    let detail = `${response.status} ${response.statusText}`;
    try {
      const body = (await response.json()) as { detail?: string | string[] };
      if (body.detail) {
        detail = Array.isArray(body.detail) ? body.detail.join("; ") : body.detail;
      }
    } catch {
      // Preserve HTTP status when the response is not JSON.
    }
    throw new Error(detail);
  }
  return (await response.json()) as T;
}

export function getHealth(): Promise<SystemHealth> {
  return request<SystemHealth>("/api/v1/health");
}

export function createMission(form: MissionForm): Promise<MissionRecord> {
  const payload = {
    schema_version: "pe.mission-control.launch.v1",
    name: form.name,
    mission_type: "web_test",
    governance_mode: form.governance_mode,
    persona_binding: {
      persona_id: "test-executor",
      version: "1.0.0",
    },
    tool: {
      adapter_id: "selenium",
      action: "run",
      parameters: {
        scenario: form.scenario,
        target_url: form.target_url,
        browser: form.browser,
        headless: form.headless,
        timeout_seconds: form.timeout_seconds,
      },
    },
    objectives: [
      "Authenticate as the standard user",
      "Complete the checkout smoke flow",
      "Capture auditable mission evidence",
    ],
    constraints: {
      allowed_hosts: [new URL(form.target_url).hostname],
      destructive_actions: false,
      evidence_required: true,
    },
    telemetry: {
      capture_token_usage: true,
      capture_duration: true,
      capture_tool_calls: true,
    },
  };
  return request<MissionRecord>("/api/v1/missions", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function getMission(missionId: string): Promise<MissionRecord> {
  return request<MissionRecord>(`/api/v1/missions/${missionId}`);
}

export function getMissionEvents(missionId: string): Promise<MissionEvent[]> {
  return request<MissionEvent[]>(`/api/v1/missions/${missionId}/events`);
}

export function getEvidence(missionId: string): Promise<EvidenceManifest> {
  return request<EvidenceManifest>(
    `/api/v1/missions/${missionId}/evidence`,
  );
}

export function listBehavioralIncidents(): Promise<BehavioralIncident[]> {
  return request<BehavioralIncident[]>("/api/v1/behavioral-incidents");
}

export function createBehavioralIncident(payload: {
  mission_id?: string;
  persona_id: string;
  persona_version: string;
  classification: IncidentClassification;
  title: string;
  description: string;
  evidence_refs: string[];
  reported_by: string;
}): Promise<BehavioralIncident> {
  return request<BehavioralIncident>("/api/v1/behavioral-incidents", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function listPersonaDeltaProposals(): Promise<PersonaDeltaProposal[]> {
  return request<PersonaDeltaProposal[]>("/api/v1/persona-delta-proposals");
}

export function createPersonaDeltaProposal(payload: {
  incident_id: string;
  persona_id: string;
  base_version: string;
  proposed_version: string;
  title: string;
  hypothesis: string;
  primitive_changes: PrimitiveChange[];
  safety_constraints: string[];
  regression_objectives: string[];
  proposed_by: string;
}): Promise<PersonaDeltaProposal> {
  return request<PersonaDeltaProposal>("/api/v1/persona-delta-proposals", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function reviewPersonaDeltaProposal(
  proposalId: string,
  decision: "approve" | "reject",
  reviewerId: string,
  notes: string,
): Promise<PersonaDeltaProposal> {
  return request<PersonaDeltaProposal>(
    `/api/v1/persona-delta-proposals/${proposalId}/review`,
    {
      method: "POST",
      body: JSON.stringify({
        decision,
        reviewer_id: reviewerId,
        notes,
      }),
    },
  );
}

export function listRegressionComparisons(
  proposalId: string,
): Promise<RegressionComparison[]> {
  return request<RegressionComparison[]>(
    `/api/v1/persona-delta-proposals/${proposalId}/regression-comparisons`,
  );
}

export function createRegressionComparison(
  proposalId: string,
  payload: {
    baseline_mission_id?: string;
    candidate_mission_id?: string;
    metrics: RegressionMetric[];
    verdict: "pass" | "fail" | "incomplete";
    notes: string;
    recorded_by: string;
  },
): Promise<RegressionComparison> {
  return request<RegressionComparison>(
    `/api/v1/persona-delta-proposals/${proposalId}/regression-comparisons`,
    {
      method: "POST",
      body: JSON.stringify(payload),
    },
  );
}

export function listPersonaVersions(personaId: string): Promise<PersonaVersion[]> {
  return request<PersonaVersion[]>(
    `/api/v1/personas/${encodeURIComponent(personaId)}/versions`,
  );
}
