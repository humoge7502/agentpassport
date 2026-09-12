/** Trust Graph, Delegation Center, Security Center, Policy Center, Audit Center. */

import { useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  api, type Delegation, type DiscoveryResult, type Incident, type PolicyRule,
} from "../lib/api";
import { useQuery } from "../lib/useQuery";
import {
  Badge, Button, Card, CardHeader, DecisionBadge, EmptyState, ErrorState, Skeleton,
  StatCard, Table, Td,
} from "../components/ui";
import { TrustGraph as TrustGraphChart } from "../components/charts";
import { humanize, severityTone, shortId, when } from "../lib/format";

// --- Trust Graph ------------------------------------------------------------

export function TrustGraphPage() {
  const navigate = useNavigate();
  const { data, loading, error } = useQuery(() => api.getGraph(), []);
  if (error) return <ErrorState message={error} />;
  return (
    <div className="rise mx-auto max-w-6xl space-y-4">
      <header>
        <h1 className="text-xl font-semibold tracking-tight">Trust Graph</h1>
        <p className="mt-0.5 text-[13px] text-(--color-ink-faint)">
          Relationships between agents and organizations. Trust is <em>not</em> assumed
          transitive — propagation is capability-matched and discounted per hop.
        </p>
      </header>
      <Card>
        {loading ? <Skeleton className="m-4 h-96" /> : (
          <div className="p-3">
            <TrustGraphChart
              nodes={data?.nodes ?? []}
              edges={data?.edges ?? []}
              onSelect={(id) => navigate(`/agents/${id}`)}
            />
          </div>
        )}
      </Card>
    </div>
  );
}

// --- Delegation Center ---------------------------------------------------------

export function DelegationCenter() {
  const { data, loading, refetch } = useQuery(() => api.getDelegations(), []);
  const [discoverCap, setDiscoverCap] = useState("");
  const [discovery, setDiscovery] = useState<{ results: DiscoveryResult[] } | null>(null);
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState<string | null>(null);

  const delegs: Delegation[] = data?.delegations ?? [];

  const runDiscovery = async () => {
    if (!discoverCap.trim()) return;
    setBusy(true);
    try {
      setDiscovery(await api.discover(discoverCap.trim()));
    } catch (e) {
      setNote(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  const act = async (label: string, fn: () => Promise<unknown>) => {
    setBusy(true);
    try {
      await fn();
      setNote(label);
      refetch();
    } catch (e) {
      setNote(`${label} failed: ${e instanceof Error ? e.message : e}`);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="rise mx-auto max-w-6xl space-y-4">
      <header>
        <h1 className="text-xl font-semibold tracking-tight">Delegation Center</h1>
        <p className="mt-0.5 text-[13px] text-(--color-ink-faint)">
          Find agents by capability, rank by contextual trust, gate by policy — every
          decision carries its reasons.
        </p>
      </header>

      <Card>
        <CardHeader title="Discovery" subtitle="ranked by contextual trust, not popularity" />
        <div className="flex flex-wrap items-center gap-2 px-4 py-3">
          <input
            value={discoverCap}
            onChange={(e) => setDiscoverCap(e.target.value)}
            placeholder="capability — e.g. vendor_negotiation"
            className="w-64 rounded-(--radius-sm) border border-(--color-line) bg-(--color-bg) px-2.5 py-1.5 text-[13px] outline-none placeholder:text-(--color-ink-faint) focus:border-(--color-accent)"
            aria-label="capability to discover"
          />
          <Button variant="primary" onClick={runDiscovery} disabled={busy || !discoverCap.trim()}>
            Find candidates
          </Button>
          {note && <p role="status" className="text-xs text-(--color-ink-faint)">{note}</p>}
        </div>
        {discovery && (
          <DiscoveryTable results={discovery.results} />
        )}
      </Card>

      <Card>
        <CardHeader title="Delegation history" subtitle="full decision records" />
        {loading ? (
          <div className="space-y-2 p-4">{Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-10" />)}</div>
        ) : delegs.length === 0 ? (
          <EmptyState title="No delegations yet" hint="Run discovery above or call POST /delegations/evaluate." />
        ) : (
          <Table headers={["Capability", "Requester → Delegate", "Value", "Decision", "Status", "Reasons", "When", ""]} caption="delegations">
            {delegs.map((d) => (
              <tr key={d.delegation_id} className="align-top hover:bg-(--color-surface-2)">
                <Td className="font-medium text-(--color-ink)">{d.capability}</Td>
                <Td mono className="text-xs">{shortId(d.requester_agent_id, 6)} → {shortId(d.delegate_agent_id, 6)}</Td>
                <Td mono className="text-xs">{d.transaction_value !== null ? d.transaction_value.toLocaleString() : "—"}</Td>
                <Td><DecisionBadge decision={d.decision} /></Td>
                <Td className="text-xs">{humanize(d.status)}</Td>
                <Td className="max-w-72">
                  <ul className="list-inside list-disc space-y-0.5 text-[11px] text-(--color-ink-faint)">
                    {d.decision_detail?.reasons?.slice(0, 3).map((r) => (
                      <li key={r.code}>{r.detail}</li>
                    ))}
                  </ul>
                </Td>
                <Td className="text-xs">{when(d.created_at)}</Td>
                <Td>
                  <div className="flex gap-1.5">
                    {d.status === "pending_approval" && (
                      <Button onClick={() => act("Approved", () => api.approveDelegation(d.delegation_id))} disabled={busy}>
                        Approve
                      </Button>
                    )}
                    {(d.status === "approved" || d.status === "pending_approval") && (
                      <Button variant="primary" onClick={() => act("Marked executed", () => api.completeDelegation(d.delegation_id, "completed"))} disabled={busy}>
                        Complete
                      </Button>
                    )}
                  </div>
                </Td>
              </tr>
            ))}
          </Table>
        )}
      </Card>
    </div>
  );
}

function DiscoveryTable({ results }: { results: DiscoveryResult[] }) {
  if (results.length === 0) {
    return <EmptyState title="No candidates found" hint="No active agent declares this capability, or none passes policy." />;
  }
  return (
    <Table headers={["Rank", "Agent", "Score", "Confidence", "Security", "Decision", "Meets floor", "Why"]} caption="discovery results">
      {results.map((r, i) => (
        <tr key={r.agent_id} className="hover:bg-(--color-surface-2)">
          <Td mono>{i + 1}</Td>
          <Td>
            <span className="font-medium text-(--color-ink)">{r.display_name}</span>
            <span className="ml-2 mono text-[11px] text-(--color-ink-faint)">{shortId(r.agent_id, 8)}</span>
          </Td>
          <Td mono>{r.score !== null ? r.score.toFixed(1) : "UNKNOWN"}</Td>
          <Td mono>{r.confidence !== null ? `${(r.confidence * 100).toFixed(0)}%` : "—"}</Td>
          <Td mono>{r.security_score !== null ? r.security_score.toFixed(0) : "—"}</Td>
          <Td><DecisionBadge decision={r.decision} /></Td>
          <Td>
            <Badge tone={r.meets_confidence_floor ? "allow" : "condition"}>
              {r.meets_confidence_floor ? "yes" : "below"}
            </Badge>
          </Td>
          <Td className="max-w-64">
            <ul className="list-inside list-disc text-[11px] text-(--color-ink-faint)">
              {r.reasons.slice(0, 2).map((x) => <li key={x.code}>{x.detail}</li>)}
            </ul>
          </Td>
        </tr>
      ))}
    </Table>
  );
}

// --- Security Center -------------------------------------------------------------

export function SecurityCenter() {
  const { data, loading, error, refetch } = useQuery(() => api.getIncidents(), []);
  const [busy, setBusy] = useState(false);
  const [scanNote, setScanNote] = useState<string | null>(null);

  const incidents: Incident[] = data?.incidents ?? [];
  const open = incidents.filter((i) => i.status === "open");

  const scan = async () => {
    setBusy(true);
    setScanNote(null);
    try {
      const res = await api.runSecurityScan();
      const created = (res as { incidents_created?: string[] }).incidents_created ?? [];
      setScanNote(`scan complete — ${created.length} new incident(s) recorded`);
      refetch();
    } catch (e) {
      setScanNote(`scan failed: ${e instanceof Error ? e.message : e}`);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="rise mx-auto max-w-6xl space-y-4">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold tracking-tight">Security Center</h1>
          <p className="mt-0.5 text-[13px] text-(--color-ink-faint)">
            Sybil clusters, collusion cycles, lineage risk — detection heuristics, honestly labeled.
          </p>
        </div>
        <Button variant="primary" onClick={scan} disabled={busy}>
          Run graph scan
        </Button>
      </header>
      {scanNote && (
        <p role="status" className="rounded-(--radius-sm) border border-(--color-line) bg-(--color-surface-2) px-3 py-2 text-xs text-(--color-ink-dim)">
          {scanNote}
        </p>
      )}

      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <StatCard label="Open incidents" value={open.length} tone={open.length ? "deny" : "allow"} />
        <StatCard label="Collusion" value={incidents.filter((i) => i.kind === "collusion").length} tone="condition" />
        <StatCard label="Sybil signals" value={incidents.filter((i) => i.kind === "sybil").length} />
        <StatCard label="Total recorded" value={incidents.length} />
      </div>

      {error ? <ErrorState message={error} /> : (
        <Card>
          <CardHeader title="Incidents" subtitle="open + historical" />
          {loading ? (
            <div className="space-y-2 p-4">{Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-10" />)}</div>
          ) : incidents.length === 0 ? (
            <EmptyState title="No incidents recorded" hint="Run a graph scan to detect collusion and Sybil clusters." />
          ) : (
            <Table headers={["Kind", "Severity", "Status", "Detail", "Detected"]} caption="security incidents">
              {incidents.map((i) => (
                <tr key={i.incident_id} className="hover:bg-(--color-surface-2)">
                  <Td><Badge tone={severityTone(i.severity)}>{humanize(i.kind)}</Badge></Td>
                  <Td>{i.severity}</Td>
                  <Td><Badge tone={i.status === "open" ? "condition" : "unknown"}>{i.status}</Badge></Td>
                  <Td className="max-w-[28rem] truncate text-xs" mono>{JSON.stringify(i.detail)}</Td>
                  <Td className="text-xs">{when(i.detected_at)}</Td>
                </tr>
              ))}
            </Table>
          )}
        </Card>
      )}
    </div>
  );
}

// --- Policy Center ------------------------------------------------------------------

export function PolicyCenter() {
  const { data, loading, error } = useQuery(() => api.getPolicies(), []);
  const rules: PolicyRule[] = data?.rules ?? [];
  return (
    <div className="rise mx-auto max-w-6xl space-y-4">
      <header>
        <h1 className="text-xl font-semibold tracking-tight">Policy Center</h1>
        <p className="mt-0.5 text-[13px] text-(--color-ink-faint)">
          Built-in rules evaluate first (lowest priority number wins); DB rules layer on
          top. Thresholds live in TrustConfig — no magic numbers in the engine.
        </p>
      </header>
      {error ? <ErrorState message={error} /> : (
        <Card>
          <CardHeader title="Custom rules" subtitle="stored in policy_rules" />
          {loading ? (
            <div className="space-y-2 p-4">{Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} className="h-9" />)}</div>
          ) : rules.length === 0 ? (
            <EmptyState
              title="No custom rules"
              hint="Built-in policy is active: security floor, score/confidence thresholds by risk class, high-value human approval, reverify gating. Add rules via PUT /policies/{rule_id}."
            />
          ) : (
            <Table headers={["Rule", "Outcome", "Priority", "Matcher", "Enabled"]} caption="policy rules">
              {rules.map((r) => (
                <tr key={r.rule_id} className="hover:bg-(--color-surface-2)">
                  <Td className="font-medium text-(--color-ink)">{r.name}</Td>
                  <Td><DecisionBadge decision={r.outcome} /></Td>
                  <Td mono>{r.priority}</Td>
                  <Td mono className="max-w-96 truncate text-xs">{JSON.stringify(r.matcher)}</Td>
                  <Td><Badge tone={r.enabled ? "allow" : "unknown"}>{r.enabled ? "on" : "off"}</Badge></Td>
                </tr>
              ))}
            </Table>
          )}
        </Card>
      )}
    </div>
  );
}

// --- Audit Center -----------------------------------------------------------------

export function AuditCenter() {
  const [entityType, setEntityType] = useState("");
  const { data, loading, error } = useQuery(
    () => api.getAudit({ entity_type: entityType || undefined }),
    [entityType],
  );
  const events = data?.events ?? [];
  return (
    <div className="rise mx-auto max-w-6xl space-y-4">
      <header>
        <h1 className="text-xl font-semibold tracking-tight">Audit Center</h1>
        <p className="mt-0.5 text-[13px] text-(--color-ink-faint)">
          Every security-sensitive state change: who, what, when, before → after, why.
        </p>
      </header>
      <Card as="div" className="flex items-center gap-3 px-4 py-3">
        <label className="text-[11px] tracking-wide text-(--color-ink-faint) uppercase" htmlFor="etype">
          entity type
        </label>
        <select
          id="etype"
          value={entityType}
          onChange={(e) => setEntityType(e.target.value)}
          className="rounded-(--radius-sm) border border-(--color-line) bg-(--color-bg) px-2.5 py-1.5 text-[13px] outline-none focus:border-(--color-accent)"
        >
          <option value="">all</option>
          <option value="agent">agent</option>
          <option value="policy_rule">policy rule</option>
          <option value="delegation">delegation</option>
          <option value="signing_key">signing key</option>
        </select>
        <p className="ml-auto text-xs text-(--color-ink-faint)">{loading ? "…" : `${events.length} events`}</p>
      </Card>
      {error ? <ErrorState message={error} /> : (
        <Card>
          {loading ? (
            <div className="space-y-2 p-4">{Array.from({ length: 6 }).map((_, i) => <Skeleton key={i} className="h-9" />)}</div>
          ) : events.length === 0 ? (
            <EmptyState title="No audit events" hint="Create an agent or change a policy to generate audit rows." />
          ) : (
            <Table headers={["When", "Actor", "Action", "Entity", "Before → After", "Why"]} caption="audit trail">
              {events.map((a) => (
                <tr key={a.audit_id} className="align-top hover:bg-(--color-surface-2)">
                  <Td className="text-xs whitespace-nowrap">{when(a.created_at)}</Td>
                  <Td className="text-xs">{a.actor}</Td>
                  <Td><Badge tone="unknown" mono>{a.action}</Badge></Td>
                  <Td mono className="text-xs">{a.entity_type}:{shortId(a.entity_id, 8)}</Td>
                  <Td className="max-w-80">
                    <span className="mono text-[11px] text-(--color-ink-faint)">
                      {a.before ? JSON.stringify(a.before).slice(0, 90) : "∅"}
                      {" → "}
                      {a.after ? JSON.stringify(a.after).slice(0, 90) : "∅"}
                    </span>
                  </Td>
                  <Td className="text-xs">{a.why ?? "—"}</Td>
                </tr>
              ))}
            </Table>
          )}
        </Card>
      )}
    </div>
  );
}
