export type GovernanceMode = "governed" | "ungoverned";
export type MissionState =
  | "accepted"
  | "authorized"
  | "running"
  | "completed"
  | "failed"
  | "cancelled";

export interface AdapterHealth {
  adapter_id: string;
  status: "healthy" | "degraded";
  execution_mode: "fixture" | "real";
  details: Record<string, unknown>;
}

export interface SystemHealth {
  status: "healthy" | "degraded";
  service: string;
  version: string;
  execution_mode: "fixture" | "real";
  adapters: AdapterHealth[];
}

export interface TokenTelemetry {
  input_tokens?: number | null;
  output_tokens?: number | null;
  reasoning_tokens?: number | null;
  total_tokens?: number | null;
  estimated_cost_usd?: number | null;
  provider_reported: boolean;
}

export interface ExecutionResult {
  status: "passed" | "failed" | "cancelled" | "error";
  summary: string;
  duration_ms: number;
  exit_code?: number;
  telemetry: TokenTelemetry;
  fixture: boolean;
  error?: string;
}

export interface GovernanceDecision {
  decision: "AUTHORIZED" | "BLOCKED" | "BYPASSED";
  rationale: string;
  policy_bindings: string[];
}

export interface MissionRecord {
  mission_id: string;
  name: string;
  state: MissionState;
  governance_mode: GovernanceMode;
  adapter_id: string;
  created_at: string;
  updated_at: string;
  authorization?: GovernanceDecision;
  result?: ExecutionResult;
  error?: string;
}

export interface MissionEvent {
  sequence: number;
  timestamp: string;
  event_type: string;
  state: MissionState;
  details: Record<string, unknown>;
  event_hash: string;
}

export interface EvidenceManifest {
  mission_id: string;
  sealed?: boolean;
  manifest_hash?: string;
  ledger: {
    valid: boolean;
    event_count: number;
    terminal_hash?: string;
  };
  artifacts: Array<{
    path: string;
    size_bytes: number;
    sha256: string;
  }>;
}

export interface MissionForm {
  name: string;
  governance_mode: GovernanceMode;
  scenario: string;
  target_url: string;
  browser: string;
  headless: boolean;
  timeout_seconds: number;
}

export type IncidentClassification =
  | "behavioral_deviation"
  | "policy_violation"
  | "inconsistent_output"
  | "boundary_breach"
  | "other";

export interface BehavioralIncident {
  schema_version: "pe.behavioral-incident.v1";
  incident_id: string;
  mission_id?: string;
  persona_id: string;
  persona_version: string;
  classification: IncidentClassification;
  title: string;
  description: string;
  evidence_refs: string[];
  reported_by: string;
  status: "open" | "under_review" | "resolved" | "dismissed";
  created_at: string;
  updated_at: string;
}

export interface PrimitiveChange {
  primitive_id: string;
  operation: "add" | "replace" | "remove";
  current_value?: unknown;
  proposed_value?: unknown;
  rationale: string;
}

export interface ProposalReview {
  decision: "approve" | "reject";
  reviewer_id: string;
  notes: string;
  reviewed_at: string;
}

export interface PersonaDeltaProposal {
  schema_version: "pe.persona-delta-proposal.v1";
  proposal_id: string;
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
  status: "pending_review" | "approved" | "rejected";
  application_status: "not_applied";
  review_history: ProposalReview[];
  created_at: string;
  updated_at: string;
}

export interface RegressionMetric {
  metric: string;
  baseline: number;
  candidate: number;
  unit: string;
  objective: "increase" | "decrease" | "maintain";
  passed: boolean;
}

export interface RegressionComparison {
  schema_version: "pe.persona-regression-comparison.v1";
  comparison_id: string;
  proposal_id: string;
  persona_id: string;
  base_version: string;
  proposed_version: string;
  baseline_mission_id?: string;
  candidate_mission_id?: string;
  metrics: RegressionMetric[];
  verdict: "pass" | "fail" | "incomplete";
  notes: string;
  recorded_by: string;
  created_at: string;
}

export interface PersonaVersion {
  persona_id: string;
  version: string;
  lifecycle:
    | "active_baseline"
    | "proposed_candidate"
    | "approved_candidate"
    | "rejected_candidate";
  proposal_id?: string;
  incident_id?: string;
  approved: boolean;
  applied: boolean;
  created_at?: string;
}
