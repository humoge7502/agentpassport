/** Agent Explorer: search/filter by capability, org, status (spec §42). */

import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api, type AgentSummary } from "../lib/api";
import { useQuery } from "../lib/useQuery";
import { Badge, Card, EmptyState, ErrorState, Skeleton, Table, Td } from "../components/ui";
import { statusTone } from "../lib/format";

export function AgentExplorer() {
  const [capability, setCapability] = useState("");
  const [org, setOrg] = useState("");
  const [status, setStatus] = useState("");
  const navigate = useNavigate();

  const { data, loading, error } = useQuery(
    () => api.listAgents({ capability: capability || undefined, org: org || undefined, status: status || undefined }),
    [capability, org, status],
  );

  return (
    <div className="rise mx-auto max-w-6xl space-y-4">
      <header>
        <h1 className="text-xl font-semibold tracking-tight">Agent Explorer</h1>
        <p className="mt-0.5 text-[13px] text-(--color-ink-faint)">
          Every agent has a signed passport, an epoch history, and
          capability-conditioned reputation.
        </p>
      </header>

      <Card as="div" className="flex flex-wrap items-end gap-3 px-4 py-3">
        <Field label="Capability">
          <input
            value={capability}
            onChange={(e) => setCapability(e.target.value)}
            placeholder="e.g. translation"
            className="w-44 rounded-(--radius-sm) border border-(--color-line) bg-(--color-bg) px-2.5 py-1.5 text-[13px] outline-none placeholder:text-(--color-ink-faint) focus:border-(--color-accent)"
            aria-label="filter by capability"
          />
        </Field>
        <Field label="Organization">
          <input
            value={org}
            onChange={(e) => setOrg(e.target.value)}
            placeholder="org id"
            className="w-36 rounded-(--radius-sm) border border-(--color-line) bg-(--color-bg) px-2.5 py-1.5 text-[13px] outline-none placeholder:text-(--color-ink-faint) focus:border-(--color-accent)"
            aria-label="filter by organization"
          />
        </Field>
        <Field label="Status">
          <select
            value={status}
            onChange={(e) => setStatus(e.target.value)}
            className="rounded-(--radius-sm) border border-(--color-line) bg-(--color-bg) px-2.5 py-1.5 text-[13px] outline-none focus:border-(--color-accent)"
            aria-label="filter by status"
          >
            <option value="">any</option>
            <option value="active">active</option>
            <option value="suspended">suspended</option>
            <option value="revoked">revoked</option>
          </select>
        </Field>
        <p className="ml-auto text-xs text-(--color-ink-faint)">
          {loading ? "…" : `${data?.count ?? 0} agents`}
        </p>
      </Card>

      {error ? <ErrorState message={error} /> : (
        <Card>
          {loading ? (
            <div className="space-y-2 p-4">{Array.from({ length: 6 }).map((_, i) => <Skeleton key={i} className="h-10" />)}</div>
          ) : (data?.agents ?? []).length === 0 ? (
            <EmptyState
              title="No agents match these filters"
              hint="Clear the filters, or seed the demo world with: python -m app.demo.seed"
            />
          ) : (
            <Table headers={["Agent", "Org", "Risk", "Epoch", "Model", "Status", "Capabilities"]} caption="agents">
              {(data?.agents ?? []).map((a: AgentSummary) => (
                <tr
                  key={a.agent_id}
                  tabIndex={0}
                  className="cursor-pointer hover:bg-(--color-surface-2)"
                  onClick={() => navigate(`/agents/${a.agent_id}`)}
                  onKeyDown={(e) => e.key === "Enter" && navigate(`/agents/${a.agent_id}`)}
                >
                  <Td>
                    <Link to={`/agents/${a.agent_id}`} className="font-medium text-(--color-ink) hover:text-(--color-accent)" onClick={(e) => e.stopPropagation()}>
                      {a.display_name}
                    </Link>
                    <span className="ml-2 mono text-[11px] text-(--color-ink-faint)">{a.agent_id.slice(0, 8)}</span>
                  </Td>
                  <Td mono className="text-xs">{a.owner_org_id}</Td>
                  <Td>{a.risk_class}</Td>
                  <Td mono>#{a.epoch_number ?? "—"}</Td>
                  <Td mono className="text-xs">{a.model_id ?? "—"}</Td>
                  <Td><Badge tone={statusTone(a.status)}>{a.status}</Badge></Td>
                  <Td className="max-w-56 truncate text-xs">{a.capabilities.join(", ") || "—"}</Td>
                </tr>
              ))}
            </Table>
          )}
        </Card>
      )}
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="flex flex-col gap-1">
      <span className="text-[11px] font-medium tracking-wide text-(--color-ink-faint) uppercase">{label}</span>
      {children}
    </label>
  );
}
