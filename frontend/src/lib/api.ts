/** Typed API client for the AgentPassport backend (/api/v1). */

export const ADMIN_KEY_HEADER = { "X-API-Key": "dev-admin-key-change-me" };

export interface AgentSummary {
  agent_id: string;
  display_name: string;
  owner_org_id: string;
  status: string;
  risk_class: string;
  identity_version: number;
  epoch_number: number | null;
  capabilities: string[];
  model_id: string | null;
}

export interface PassportKey {
  key_id: string;
  public_key_b64: string;
  status: string;
  created_at: string;
}

export interface Passport {
  agent_id: string;
  owner_org_id: string;
  display_name: string;
  status: string;
  risk_class: string;
  identity_version: number;
  epoch_number: number;
  epoch_flags: Record<string, unknown>;
  model_id: string | null;
  model_family: string | null;
  capabilities: string[];
  tools: string[];
  permissions: string[];
  keys: PassportKey[];
  created_at: string;
  updated_at: string | null;
}

export interface SignedPassport {
  passport: Passport;
  platform_key_id: string;
  signature: string;
  signed_at: string;
}

export interface DimensionScore {
  score: number | null;
  confidence: number;
  n_eff: number;
  positive: number;
  negative: number;
  evidence_count: number;
}

export interface Reputation {
  agent_id: string;
  capability: string;
  computed_at: string;
  dimensions: Record<string, DimensionScore>;
}

export interface EvidenceEvent {
  event_id: string;
  seq: number;
  event_type: string;
  capability: string | null;
  task_class: string | null;
  outcome: string | null;
  issuer_type: string;
  issuer_id: string;
  quality_tier: string;
  visibility: string;
  context: Record<string, unknown>;
  event_hash: string;
  prev_event_hash: string | null;
  signature: string;
  created_at: string;
}

export interface Reason {
  code: string;
  detail: string;
  factor: string;
}

export interface Decision {
  decision: string;
  agent_id: string;
  capability: string;
  score: number | null;
  confidence: number | null;
  reasons: Reason[];
  context: Record<string, unknown>;
  evaluated_at: string;
  policy_id: string | null;
  decision_id: string | null;
}

export interface Delegation {
  delegation_id: string;
  requester_agent_id: string;
  delegate_agent_id: string;
  capability: string;
  task_class: string | null;
  transaction_value: number | null;
  risk_class: string;
  decision: string;
  decision_detail: Decision;
  status: string;
  created_at: string;
  closed_at: string | null;
}

export interface Incident {
  incident_id: string;
  agent_id: string | null;
  kind: string;
  severity: string;
  detail: Record<string, unknown>;
  status: string;
  detected_at: string;
}

export interface AuditRow {
  audit_id: string;
  actor: string;
  action: string;
  entity_type: string;
  entity_id: string;
  before: Record<string, unknown> | null;
  after: Record<string, unknown> | null;
  why: string | null;
  correlation_id: string | null;
  created_at: string;
}

export interface TrustEdge {
  id: string;
  source: string;
  target: string;
  capability: string;
  strength: number;
  confidence: number;
  kind: string;
}

export interface GraphNode {
  id: string;
  label: string;
  org: string;
  status: string;
}

export interface Epoch {
  epoch_id: string;
  epoch_number: number;
  trigger: string;
  started_at: string;
  ended_at: string | null;
  config: Record<string, unknown>;
  continuity: {
    dimensions?: Record<string, number>;
    factor?: number;
    reverify?: boolean;
    reasons?: string[];
  } | null;
  reputation_baseline: Record<string, unknown> | null;
  flags: Record<string, unknown>;
}

export interface DiscoveryResult {
  agent_id: string;
  display_name: string;
  owner_org_id: string;
  risk_class: string;
  score: number | null;
  confidence: number | null;
  security_score: number | null;
  evidence_count: number | null;
  decision: string;
  reasons: Reason[];
  meets_confidence_floor: boolean;
}

export interface PolicyRule {
  rule_id: string;
  name: string;
  outcome: string;
  priority: number;
  matcher: Record<string, unknown>;
  enabled: boolean;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`/api/v1${path}`, init);
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail?.message ?? body.detail ?? JSON.stringify(body);
    } catch {
      /* keep statusText */
    }
    throw new Error(`${res.status}: ${detail}`);
  }
  return res.json() as Promise<T>;
}

const q = (params: Record<string, string | number | undefined | null>) => {
  const usp = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== null && v !== "") usp.set(k, String(v));
  }
  const s = usp.toString();
  return s ? `?${s}` : "";
};

export const api = {
  // reads
  listAgents: (params: { capability?: string; status?: string; org?: string } = {}) =>
    request<{ agents: AgentSummary[]; count: number }>(`/agents${q(params)}`),
  getPassport: (id: string) => request<SignedPassport>(`/agents/${id}/passport`),
  getReputation: (id: string) =>
    request<{ reputations: Record<string, Reputation> }>(`/agents/${id}/reputation`),
  getEvidence: (id: string, visibility = "org") =>
    request<{ events: EvidenceEvent[] }>(`/agents/${id}/evidence${q({ visibility })}`),
  getEpochs: (id: string) => request<{ epochs: Epoch[] }>(`/agents/${id}/epochs`),
  getGraph: () =>
    request<{ nodes: GraphNode[]; edges: TrustEdge[] }>("/trust/graph"),
  getDelegations: () => request<{ delegations: Delegation[] }>("/delegations"),
  getIncidents: () => request<{ incidents: Incident[] }>("/security/incidents"),
  getAudit: (params: { entity_type?: string; entity_id?: string } = {}) =>
    request<{ events: AuditRow[] }>(`/audit${q(params)}`),
  getPolicies: () => request<{ rules: PolicyRule[] }>("/policies"),
  discover: (capability: string, risk_class = "medium") =>
    request<{ capability: string; results: DiscoveryResult[] }>(
      `/agents/discover${q({ capability, risk_class })}`,
    ),
  overview: async () => {
    const [agents, incidents, delegations] = await Promise.all([
      api.listAgents(),
      api.getIncidents(),
      api.getDelegations(),
    ]);
    return { agents: agents.agents, incidents: incidents.incidents, delegations: delegations.delegations };
  },

  // mutations (admin key)
  submitEvidence: (body: Record<string, unknown>) =>
    request<{ event_id: string; seq: number; event_hash: string }>("/evidence", {
      method: "POST",
      headers: { "Content-Type": "application/json", ...ADMIN_KEY_HEADER },
      body: JSON.stringify(body),
    }),
  updateAgent: (id: string, body: Record<string, unknown>) =>
    request<Record<string, unknown>>(`/agents/${id}/update`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...ADMIN_KEY_HEADER },
      body: JSON.stringify(body),
    }),
  proposeDelegation: (body: Record<string, unknown>) =>
    request<Record<string, unknown>>("/delegations/evaluate", {
      method: "POST",
      headers: { "Content-Type": "application/json", ...ADMIN_KEY_HEADER },
      body: JSON.stringify(body),
    }),
  approveDelegation: (id: string) =>
    request<Delegation>(`/delegations/${id}/approve`, {
      method: "POST",
      headers: ADMIN_KEY_HEADER,
    }),
  completeDelegation: (id: string, outcome: string) =>
    request<Delegation>(`/delegations/${id}/complete`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...ADMIN_KEY_HEADER },
      body: JSON.stringify({ outcome }),
    }),
  runSecurityScan: () =>
    request<Record<string, unknown>>("/security/scan", {
      method: "POST",
      headers: ADMIN_KEY_HEADER,
    }),
  snapshotReputation: (id: string) =>
    request<{ snapshots: number }>(`/agents/${id}/reputation/snapshot`, {
      method: "POST",
      headers: ADMIN_KEY_HEADER,
    }),
};
