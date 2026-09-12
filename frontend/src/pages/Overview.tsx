/** Overview: system health at a glance (spec §42). */

import { Link } from "react-router-dom";
import { api, type AgentSummary, type Delegation, type Incident } from "../lib/api";
import { useQuery } from "../lib/useQuery";
import { Badge, Card, CardHeader, DecisionBadge, ErrorState, Skeleton, StatCard, Table, Td } from "../components/ui";
import { statusTone, severityTone, when, shortId } from "../lib/format";

export function Overview() {
  const { data, loading, error } = useQuery(async () => {
    const [agents, incidents, delegations] = await Promise.all([
      api.listAgents(),
      api.getIncidents(),
      api.getDelegations(),
    ]);
    return {
      agents: agents.agents,
      incidents: incidents.incidents,
      delegations: delegations.delegations,
    };
  }, []);

  if (error) return <ErrorState message={error} />;

  const agents = data?.agents ?? [];
  const open = (data?.incidents ?? []).filter((i) => i.status === "open");
  const recentDelegs = (data?.delegations ?? []).slice(0, 6);

  return (
    <div className="rise mx-auto max-w-6xl space-y-5">
      <header>
        <h1 className="text-xl font-semibold tracking-tight">Overview</h1>
        <p className="mt-0.5 text-[13px] text-(--color-ink-faint)">
          Should agent A be trusted to do X, in context Y, at time T? Everything here
          exists to answer that question — with evidence, not vibes.
        </p>
      </header>

      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        {loading ? (
          Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-20" />)
        ) : (
          <>
            <StatCard label="Registered agents" value={agents.length}
              hint={`${agents.filter((a) => a.status === "active").length} active`}
              tone={agents.some((a) => a.status === "active") ? "allow" : "unknown"} />
            <StatCard label="Open incidents" value={open.length}
              hint={open.length ? "requires review" : "no open incidents"}
              tone={open.length ? "deny" : "allow"} />
            <StatCard label="Delegations" value={(data?.delegations ?? []).length}
              hint="lifetime evaluations" />
            <StatCard label="Trust epochs" value={new Set(agents.map((a) => a.epoch_number)).size}
              hint="distinct epoch counts" />
          </>
        )}
      </div>

      <div className="grid gap-5 lg:grid-cols-2">
        <Card>
          <CardHeader
            title="Agents"
            subtitle="trust is per-capability, not global"
            action={
              <Link to="/agents" className="text-xs text-(--color-accent) hover:underline">
                explorer →
              </Link>
            }
          />
          {loading ? (
            <div className="space-y-2 p-4">
              {Array.from({ length: 5 }).map((_, i) => <Skeleton key={i} className="h-9" />)}
            </div>
          ) : (
            <Table headers={["Agent", "Org", "Epoch", "Status", "Capabilities"]} caption="registered agents">
              {agents.slice(0, 8).map((a: AgentSummary) => (
                <tr key={a.agent_id} className="hover:bg-(--color-surface-2)">
                  <Td>
                    <Link to={`/agents/${a.agent_id}`} className="font-medium text-(--color-ink) hover:text-(--color-accent)">
                      {a.display_name}
                    </Link>
                  </Td>
                  <Td mono>{shortId(a.owner_org_id, 10)}</Td>
                  <Td mono>#{a.epoch_number ?? "—"}</Td>
                  <Td><Badge tone={statusTone(a.status)}>{a.status}</Badge></Td>
                  <Td className="max-w-40 truncate text-xs">{a.capabilities.join(", ") || "—"}</Td>
                </tr>
              ))}
            </Table>
          )}
        </Card>

        <Card>
          <CardHeader
            title="Delegation activity"
            subtitle="every decision is explainable"
            action={
              <Link to="/delegations" className="text-xs text-(--color-accent) hover:underline">
                center →
              </Link>
            }
          />
          {loading ? (
            <div className="space-y-2 p-4">
              {Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-9" />)}
            </div>
          ) : recentDelegs.length === 0 ? (
            <div className="px-4 py-10 text-center text-xs text-(--color-ink-faint)">
              No delegations evaluated yet.
            </div>
          ) : (
            <Table headers={["Capability", "Delegate", "Decision", "Status", "When"]} caption="recent delegations">
              {recentDelegs.map((d: Delegation) => (
                <tr key={d.delegation_id} className="hover:bg-(--color-surface-2)">
                  <Td className="font-medium text-(--color-ink)">{d.capability}</Td>
                  <Td mono>{shortId(d.delegate_agent_id, 8)}</Td>
                  <Td><DecisionBadge decision={d.decision} /></Td>
                  <Td className="text-xs">{d.status.replace(/_/g, " ")}</Td>
                  <Td className="text-xs">{when(d.created_at)}</Td>
                </tr>
              ))}
            </Table>
          )}
        </Card>
      </div>

      <Card>
        <CardHeader title="Security signals" subtitle="collusion, sybil, and lineage alerts" action={
          <Link to="/security" className="text-xs text-(--color-accent) hover:underline">security center →</Link>
        } />
        {loading ? (
          <div className="space-y-2 p-4">{Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} className="h-9" />)}</div>
        ) : open.length === 0 ? (
          <div className="px-4 py-8 text-center text-xs text-(--color-ink-faint)">
            No open incidents. Run a scan from the Security Center.
          </div>
        ) : (
          <Table headers={["Kind", "Severity", "Detail", "Detected"]} caption="open incidents">
            {open.slice(0, 6).map((i: Incident) => (
              <tr key={i.incident_id} className="hover:bg-(--color-surface-2)">
                <Td><Badge tone={severityTone(i.severity)}>{i.kind}</Badge></Td>
                <Td>{i.severity}</Td>
                <Td className="max-w-96 truncate text-xs">{JSON.stringify(i.detail)}</Td>
                <Td className="text-xs">{when(i.detected_at)}</Td>
              </tr>
            ))}
          </Table>
        )}
      </Card>
    </div>
  );
}
