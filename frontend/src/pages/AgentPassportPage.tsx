/** Agent Passport: identity, capabilities, reputation vector, epochs, evidence,
 *  with progressive disclosure and explainable trust (spec §42/§43/§64). */

import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import {
  api, type Decision, type Epoch, type EvidenceEvent, type Reputation, type SignedPassport,
} from "../lib/api";
import { useQuery } from "../lib/useQuery";
import {
  Badge, Button, Card, CardHeader, ConfidenceBar, EmptyState, ErrorState, KeyValue,
  Skeleton, Table, Td,
} from "../components/ui";
import { ChainStrip, VectorRadar } from "../components/charts";
import { decisionTone, humanize, pct, score, shortId, statusTone, when } from "../lib/format";

const TABS = ["passport", "reputation", "evidence", "epochs"] as const;
type Tab = (typeof TABS)[number];

export function AgentPassportPage() {
  const { id = "" } = useParams();
  const [tab, setTab] = useState<Tab>("passport");
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState<string | null>(null);

  const passport = useQuery(() => api.getPassport(id), [id]);
  const reputation = useQuery(() => api.getReputation(id), [id]);
  const evidence = useQuery(() => api.getEvidence(id, "org"), [id]);
  const epochs = useQuery(() => api.getEpochs(id), [id]);

  if (passport.error) return <ErrorState message={passport.error} />;
  if (passport.loading || !passport.data) {
    return (
      <div className="mx-auto max-w-6xl space-y-4">
        <Skeleton className="h-8 w-72" />
        <div className="grid gap-4 lg:grid-cols-3">
          <Skeleton className="h-64" /><Skeleton className="h-64" /><Skeleton className="h-64" />
        </div>
      </div>
    );
  }

  const sp: SignedPassport = passport.data;
  const p = sp.passport;
  const reps: Record<string, Reputation> = reputation.data?.reputations ?? {};
  const events: EvidenceEvent[] = evidence.data?.events ?? [];
  const epochList: Epoch[] = epochs.data?.epochs ?? [];

  const act = async (label: string, fn: () => Promise<unknown>) => {
    setBusy(true);
    setNote(null);
    try {
      await fn();
      setNote(`${label} — done`);
      passport.refetch();
      reputation.refetch();
      evidence.refetch();
      epochs.refetch();
    } catch (e) {
      setNote(`${label} failed: ${e instanceof Error ? e.message : e}`);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="rise mx-auto max-w-6xl space-y-4">
      {/* identity header */}
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-xl font-semibold tracking-tight">{p.display_name}</h1>
            <Badge tone={statusTone(p.status)}>{p.status}</Badge>
            {Boolean(p.epoch_flags?.reverify) && (
              <Badge tone="condition">REVERIFY REQUIRED</Badge>
            )}
          </div>
          <p className="mt-1 mono text-xs text-(--color-ink-faint)">
            {p.agent_id} · org {p.owner_org_id} · epoch #{p.epoch_number} · v{p.identity_version} · risk {p.risk_class}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button
            variant="primary"
            disabled={busy}
            onClick={() => act("Snapshot reputation", () => api.snapshotReputation(p.agent_id))}
            ariaLabel="compute reputation snapshot"
          >
            Snapshot reputation
          </Button>
          <Button
            disabled={busy}
            onClick={() => act("Simulate model change", () =>
              api.updateAgent(p.agent_id, {
                trigger: "model_changed",
                model_id: `model-${Date.now() % 100}`,
              }))}
            ariaLabel="simulate a model change to see trust recalculation"
          >
            Simulate model change
          </Button>
          <Button
            disabled={busy}
            onClick={() => act("Rotate keys", () =>
              fetch(`/api/v1/agents/${p.agent_id}/keys/rotate`, {
                method: "POST", headers: { "X-API-Key": "dev-admin-key-change-me" },
              }))}
            ariaLabel="rotate signing keys"
          >
            Rotate keys
          </Button>
        </div>
      </header>
      {note && (
        <p role="status" className="rounded-(--radius-sm) border border-(--color-line) bg-(--color-surface-2) px-3 py-2 text-xs text-(--color-ink-dim)">
          {note}
        </p>
      )}

      {/* tabs */}
      <div role="tablist" aria-label="Passport sections" className="flex gap-1 border-b border-(--color-line-soft)">
        {TABS.map((t) => (
          <button
            key={t}
            role="tab"
            aria-selected={tab === t}
            onClick={() => setTab(t)}
            className={`-mb-px rounded-t-(--radius-sm) border-b-2 px-3 py-2 text-[13px] transition-colors duration-150 ${
              tab === t
                ? "border-(--color-accent) font-medium text-(--color-ink)"
                : "border-transparent text-(--color-ink-faint) hover:text-(--color-ink-dim)"
            }`}
          >
            {t === "passport" ? "Passport" : t === "reputation" ? "Reputation" : t}
          </button>
        ))}
      </div>

      {tab === "passport" && (
        <div className="grid gap-4 lg:grid-cols-3">
          <Card>
            <CardHeader title="Identity" subtitle="platform-signed passport document" />
            <div className="px-4 py-2">
              <KeyValue k="agent id" v={p.agent_id} />
              <KeyValue k="owner" v={p.owner_org_id} />
              <KeyValue k="model" v={p.model_id ?? "—"} />
              <KeyValue k="model family" v={p.model_family ?? "—"} />
              <KeyValue k="identity version" v={`v${p.identity_version}`} />
              <KeyValue k="trust epoch" v={`#${p.epoch_number}`} />
              <KeyValue k="created" v={when(p.created_at)} />
              <KeyValue k="signature" v={<span title={sp.signature}>{shortId(sp.signature, 12)}…</span>} />
            </div>
          </Card>

          <Card>
            <CardHeader title="Capabilities & permissions" subtitle="what this agent may do" />
            <div className="space-y-3 px-4 py-3">
              <div>
                <p className="mb-1.5 text-[11px] tracking-wide text-(--color-ink-faint) uppercase">Capabilities</p>
                <div className="flex flex-wrap gap-1.5">
                  {p.capabilities.length === 0 && <span className="text-xs text-(--color-ink-faint)">none declared</span>}
                  {p.capabilities.map((c) => (
                    <Badge key={c} tone="unknown" mono>{c}</Badge>
                  ))}
                </div>
              </div>
              <div>
                <p className="mb-1.5 text-[11px] tracking-wide text-(--color-ink-faint) uppercase">Tools</p>
                <div className="flex flex-wrap gap-1.5">
                  {p.tools.length === 0 && <span className="text-xs text-(--color-ink-faint)">none</span>}
                  {p.tools.map((t) => <Badge key={t} mono>{t}</Badge>)}
                </div>
              </div>
              <div>
                <p className="mb-1.5 text-[11px] tracking-wide text-(--color-ink-faint) uppercase">Permissions</p>
                <div className="flex flex-wrap gap-1.5">
                  {p.permissions.length === 0 && <span className="text-xs text-(--color-ink-faint)">none</span>}
                  {p.permissions.map((t) => <Badge key={t} mono>{t}</Badge>)}
                </div>
              </div>
              <div>
                <p className="mb-1.5 text-[11px] tracking-wide text-(--color-ink-faint) uppercase">Keys</p>
                <ul className="space-y-1">
                  {p.keys.map((k) => (
                    <li key={k.key_id} className="flex items-center justify-between gap-2 text-xs">
                      <span className="mono">{shortId(k.key_id, 14)}</span>
                      <Badge tone={k.status === "active" ? "allow" : k.status === "revoked" ? "deny" : "unknown"}>{k.status}</Badge>
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          </Card>

          <Card>
            <CardHeader title="Trust at a glance" subtitle="overall across dimensions" />
            <div className="px-4 py-4">
              {Object.keys(reps).length === 0 ? (
                <EmptyState title="No reputation yet" hint="Submit evidence, then snapshot." />
              ) : (
                <OverallView reps={reps} />
              )}
            </div>
          </Card>
        </div>
      )}

      {tab === "reputation" && <ReputationTab reps={reps} loading={reputation.loading} />}

      {tab === "evidence" && (
        <Card>
          <CardHeader
            title="Evidence ledger"
            subtitle="append-only · hash-chained · signed — private rows hidden from public views"
            action={events.length > 1 ? <ChainStrip events={[...events].reverse()} /> : undefined}
          />
          {evidence.loading ? (
            <div className="space-y-2 p-4">{Array.from({ length: 6 }).map((_, i) => <Skeleton key={i} className="h-8" />)}</div>
          ) : events.length === 0 ? (
            <EmptyState title="No visible evidence" hint="Public/org events will appear here; private rows require elevated access." />
          ) : (
            <Table headers={["#", "Type", "Capability", "Issuer", "Quality", "Hash", "When"]} caption="evidence events">
              {events.map((e) => (
                <tr key={e.event_id} className="hover:bg-(--color-surface-2)">
                  <Td mono>{e.seq}</Td>
                  <Td className="font-medium text-(--color-ink)">{humanize(e.event_type)}</Td>
                  <Td className="text-xs">{e.capability ?? "—"}</Td>
                  <Td mono className="text-xs">{shortId(e.issuer_id, 12)}</Td>
                  <Td><Badge tone={e.quality_tier === "self_reported" ? "condition" : "unknown"}>{e.quality_tier.replace(/_/g, " ")}</Badge></Td>
                  <Td mono className="text-xs">{shortId(e.event_hash, 10)}…</Td>
                  <Td className="text-xs">{when(e.created_at)}</Td>
                </tr>
              ))}
            </Table>
          )}
        </Card>
      )}

      {tab === "epochs" && <EpochsTab epochs={epochList} loading={epochs.loading} />}
    </div>
  );
}

function OverallView({ reps }: { reps: Record<string, Reputation> }) {
  const entries = Object.entries(reps);
  return (
    <div className="space-y-3">
      {entries.map(([cap, rep]) => {
        const dims = Object.values(rep.dimensions);
        const known = dims.filter((d) => d.score !== null);
        const overall = known.length
          ? known.reduce((acc, d) => acc + (d.score ?? 0) * d.n_eff, 0) /
            (known.reduce((acc, d) => acc + d.n_eff, 0) || 1)
          : null;
        const conf = known.length ? Math.min(...known.map((d) => d.confidence)) : 0;
        return (
          <div key={cap} className={cap === "_global" ? "border-t border-(--color-line-soft) pt-3" : ""}>
            <div className="mb-1 flex items-center justify-between">
              <p className="text-[13px] font-medium text-(--color-ink)">
                {cap === "_global" ? "Overall (untagged)" : cap}
              </p>
              <Link to="/delegations" className="text-[11px] text-(--color-accent) hover:underline">
                why this level?
              </Link>
            </div>
            <div className="flex items-center justify-between gap-2">
              <span className="num mono text-lg font-semibold" style={{
                color: overall === null ? "var(--color-unknown)"
                  : overall >= 85 ? "var(--color-trust-5)"
                  : overall >= 60 ? "var(--color-trust-3)"
                  : "var(--color-trust-1)",
              }}>
                {score(overall)}
              </span>
              <span className="text-[11px] text-(--color-ink-faint)">
                {pct(conf, 1)} confidence · {dims.reduce((a, d) => a + d.evidence_count, 0)} events
              </span>
            </div>
            <div className="mt-1.5"><ConfidenceBar confidence={conf} /></div>
          </div>
        );
      })}
    </div>
  );
}

function ReputationTab({ reps, loading }: { reps: Record<string, Reputation>; loading: boolean }) {
  if (loading) return <Skeleton className="h-72" />;
  const caps = Object.entries(reps);
  if (caps.length === 0) return <EmptyState title="No reputation computed" hint="Snapshot after submitting evidence." />;
  return (
    <div className="grid gap-4 lg:grid-cols-2">
      {caps.map(([cap, rep]) => (
        <Card key={cap}>
          <CardHeader
            title={cap === "_global" ? "Overall (untagged evidence)" : cap}
            subtitle={`computed ${when(rep.computed_at)}`}
          />
          <div className="flex flex-col items-center gap-4 px-4 py-4 md:flex-row">
            <VectorRadar dimensions={rep.dimensions} />
            <div className="w-full flex-1 space-y-2">
              {Object.entries(rep.dimensions).map(([dim, d]) => (
                <div key={dim} title={`n_eff ${d.n_eff.toFixed(2)} · +${d.positive.toFixed(1)} / −${d.negative.toFixed(1)}`}>
                  <div className="flex items-baseline justify-between text-xs">
                    <span className="text-(--color-ink-dim)">{humanize(dim)}</span>
                    <span className="num mono" style={{ color: d.score === null ? "var(--color-unknown)" : d.score >= 80 ? "var(--color-allow)" : d.score >= 50 ? "var(--color-condition)" : "var(--color-deny)" }}>
                      {score(d.score)}
                    </span>
                  </div>
                  <div className="mt-0.5"><ConfidenceBar confidence={d.confidence} /></div>
                </div>
              ))}
            </div>
          </div>
        </Card>
      ))}
    </div>
  );
}

function EpochsTab({ epochs, loading }: { epochs: Epoch[]; loading: boolean }) {
  if (loading) return <Skeleton className="h-72" />;
  if (epochs.length === 0) return <EmptyState title="No epochs recorded" />;
  return (
    <Card>
      <CardHeader title="Trust epochs" subtitle="every material change closed an epoch — continuity is earned, not assumed" />
      <ol className="relative space-y-4 px-5 py-4">
        {epochs.map((e, i) => (
          <li key={e.epoch_id} className="relative pl-6">
            <span className="absolute top-1 left-0 flex h-3 w-3 items-center justify-center rounded-full border border-(--color-line)" aria-hidden
              style={{ background: i === epochs.length - 1 ? "var(--color-accent)" : "var(--color-surface-3)" }} />
            {i < epochs.length - 1 && <span className="absolute top-4 left-[5px] h-full w-px bg-(--color-line-soft)" aria-hidden />}
            <div className="flex flex-wrap items-baseline gap-2">
              <p className="text-[13px] font-medium text-(--color-ink)">
                Epoch #{e.epoch_number} — {humanize(e.trigger)}
              </p>
              <span className="text-[11px] text-(--color-ink-faint)">{when(e.started_at)}{e.ended_at ? ` → ${when(e.ended_at)}` : " → present"}</span>
              {e.continuity?.reverify && <Badge tone="condition">REVERIFY</Badge>}
            </div>
            {e.continuity && (
              <div className="mt-1.5 rounded-(--radius-sm) border border-(--color-line-soft) bg-(--color-surface-2) px-3 py-2">
                <p className="text-xs text-(--color-ink-dim)">
                  Inheritance factor <span className="num mono">{((e.continuity.factor ?? 0) * 100).toFixed(1)}%</span>
                  {" · "}model continuity <span className="num mono">{pct(e.continuity.dimensions?.model ?? 1)}</span>
                  {" · "}security <span className="num mono">{pct(e.continuity.dimensions?.security ?? 1)}</span>
                </p>
                {e.continuity.reasons && e.continuity.reasons.length > 0 && (
                  <ul className="mt-1 list-inside list-disc text-[11px] text-(--color-condition)">
                    {e.continuity.reasons.map((r) => <li key={r}>{r}</li>)}
                  </ul>
                )}
              </div>
            )}
            <p className="mt-1 mono text-[11px] text-(--color-ink-faint)">
              model: {String(e.config?.model_id ?? "—")} · capabilities: {(e.config?.capabilities as string[] | undefined)?.join(", ") || "—"}
            </p>
          </li>
        ))}
      </ol>
    </Card>
  );
}

export type { Decision };
export { decisionTone };
