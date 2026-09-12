/** Killer demo (spec §63/§64): a guided, live-API walkthrough.
 *
 *  1. ProcurementAgent asks: "find an agent capable of vendor negotiation"
 *  2. AgentPassport ranks candidates by contextual trust
 *  3. best candidate selected → delegation → evidence recorded
 *  4. introduce a model replacement → identity continuity YES,
 *     behavioral continuity REDUCED → decision changes — visibly.
 */

import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, type Delegation, type DiscoveryResult } from "../lib/api";
import { Button, Card, CardHeader, DecisionBadge, ErrorState } from "../components/ui";
import { shortId } from "../lib/format";

interface DemoState {
  discovery?: { results: DiscoveryResult[] };
  delegation?: Delegation;
  completed?: boolean;
  update?: Record<string, unknown>;
  delegationAfter?: Delegation;
}

export function DemoPage() {
  const [step, setStep] = useState(0);
  const [state, setState] = useState<DemoState>({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const agents = useAgentList();

  const runStep = async (next: number, fn?: () => Promise<Partial<DemoState>>) => {
    setBusy(true);
    setError(null);
    try {
      if (fn) {
        const patch = await fn();
        setState((s) => ({ ...s, ...patch }));
      }
      setStep(next);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  const negotiatorId = agents?.find((a) => a.display_name === "NegotiatorBot")?.agent_id;
  const procureId = agents?.find((a) => a.display_name === "ProcureBot")?.agent_id;

  return (
    <div className="rise mx-auto max-w-4xl space-y-4">
      <header>
        <h1 className="text-xl font-semibold tracking-tight">Killer Demo — dynamic trust</h1>
        <p className="mt-0.5 text-[13px] text-(--color-ink-faint)">
          Live walkthrough against your seeded instance. Run{" "}
          <code className="mono text-(--color-accent)">python -m app.demo.seed</code> first.
          Steps 1–3: delegation succeeds. Step 4: the delegate swaps its model. Step 5:
          watch the same request get gated.
        </p>
      </header>

      {error && <ErrorState message={error} />}

      <Step n={1} title='ProcurementAgent: "find an agent capable of vendor negotiation"'
        done={step > 1} active={step === 1}>
        <Button variant="primary" disabled={busy} onClick={() => runStep(2, async () => {
          const d = await api.discover("vendor_negotiation", "high");
          return { discovery: d };
        })}>
          Call discovery
        </Button>
        {state.discovery && <DiscoveryResults results={state.discovery.results} />}
      </Step>

      <Step n={2} title="AgentPassport ranks candidates by contextual trust"
        done={step > 2} active={step === 2}>
        {state.discovery ? (
          <DiscoveryResults results={state.discovery.results} compact />
        ) : (
          <p className="text-xs text-(--color-ink-faint)">run step 1 first</p>
        )}
        <Button variant="primary" disabled={busy || !state.discovery}
          onClick={() => runStep(3, async () => {
            const best = state.discovery!.results.find((r) => r.decision === "ALLOW") ?? state.discovery!.results[0];
            const res = await api.proposeDelegation({
              requester_agent_id: procureId ?? best.agent_id,
              delegate_agent_id: best.agent_id,
              capability: "vendor_negotiation",
              risk_class: "high",
              transaction_value: 75000,
              task_class: "vendor_negotiation.renewal",
            });
            return { delegation: (res as { delegation: Delegation }).delegation };
          })}>
          Delegate to best candidate
        </Button>
        {state.delegation && (
          <DecisionCard d={state.delegation} label="Delegation decision (before model change)" />
        )}
      </Step>

      <Step n={3} title="Agent operates → evidence recorded → reputation updated"
        done={step > 3} active={step === 3}>
        {state.delegation ? (
          <Button variant="primary" disabled={busy || state.completed}
            onClick={() => runStep(4, async () => {
              await api.completeDelegation(state.delegation!.delegation_id, "completed");
              return { completed: true };
            })}>
            Mark delegation completed
          </Button>
        ) : <p className="text-xs text-(--color-ink-faint)">complete step 2 first</p>}
        {state.completed && (
          <p className="text-xs text-(--color-allow)">
            evidence event <code className="mono">delegation_completed</code> appended to the
            delegate's hash-chained ledger.
          </p>
        )}
      </Step>

      <Step n={4} title="Model replacement — identity continuity: YES, behavioral continuity: UNKNOWN"
        done={step > 4} active={step === 4}>
        {negotiatorId ? (
          <Button variant="primary" disabled={busy || !state.completed}
            onClick={() => runStep(5, async () => {
              const upd = await api.updateAgent(negotiatorId, {
                trigger: "model_changed", model_id: "nova-7", model_family: "nova",
              });
              const res = await api.proposeDelegation({
                requester_agent_id: procureId ?? negotiatorId,
                delegate_agent_id: negotiatorId,
                capability: "vendor_negotiation",
                risk_class: "high",
                transaction_value: 75000,
                task_class: "vendor_negotiation.renewal",
              });
              return { update: upd, delegationAfter: (res as { delegation: Delegation }).delegation };
            })}>
            Swap NegotiatorBot's model → re-run same delegation
          </Button>
        ) : <p className="text-xs text-(--color-ink-faint)">seed the demo world first</p>}
        {state.update && (
          <div className="rounded-(--radius-sm) border border-(--color-line-soft) bg-(--color-surface-2) px-3 py-2">
            <p className="text-xs text-(--color-ink-dim)">
              New epoch #{String((state.update as { new_epoch_number?: number }).new_epoch_number)} ·
              inheritance factor{" "}
              <span className="num mono">
                {(((state.update as { continuity?: { factor?: number } }).continuity?.factor ?? 0) * 100).toFixed(1)}%
              </span>{" "}
              · reverify required:{" "}
              <span className="mono text-(--color-condition)">
                {String((state.update as { reverify_required?: boolean }).reverify_required)}
              </span>
            </p>
            <ul className="mt-1 list-inside list-disc text-[11px] text-(--color-ink-faint)">
              {(state.update as { continuity?: { reasons?: string[] } }).continuity?.reasons?.map((r) => (
                <li key={r}>{r}</li>
              ))}
            </ul>
          </div>
        )}
      </Step>

      <Step n={5} title="Trust decision changes — visibly" done={step > 5} active={step === 5}>
        {state.delegationAfter ? (
          <div className="space-y-3">
            <div className="grid grid-cols-1 gap-2 md:grid-cols-2">
              {state.delegation && (
                <DecisionCard d={state.delegation} label="Before model change" />
              )}
              <DecisionCard d={state.delegationAfter} label="After model change" highlight />
            </div>
            <p className="text-xs text-(--color-ink-faint)">
              Same agent id, same capability, same value — different epoch, different
              answer. Every reason is inspectable.{" "}
              {negotiatorId && (
                <Link className="text-(--color-accent) hover:underline" to={`/agents/${negotiatorId}`}>
                  Open NegotiatorBot's passport →
                </Link>
              )}
            </p>
          </div>
        ) : <p className="text-xs text-(--color-ink-faint)">complete step 4 first</p>}
      </Step>
    </div>
  );
}

function Step({
  n, title, done, active, children,
}: {
  n: number; title: string; done: boolean; active: boolean;
  children?: React.ReactNode;
}) {
  return (
    <Card className={active ? "border-(--color-accent)/40" : done ? "opacity-90" : "opacity-60"}>
      <CardHeader
        title={`${n}. ${title}`}
        action={
          <span className={`h-2 w-2 rounded-full ${done ? "bg-(--color-allow)" : active ? "pulse-soft bg-(--color-accent)" : "bg-(--color-surface-3)"}`} aria-hidden />
        }
      />
      {active && <div className="space-y-3 px-4 py-3">{children}</div>}
      {done && children && (
        <details className="px-4 py-2 text-xs text-(--color-ink-faint)">
          <summary className="cursor-pointer select-none">show step output</summary>
          <div className="pt-2">{children}</div>
        </details>
      )}
    </Card>
  );
}

function DiscoveryResults({ results, compact = false }: { results: DiscoveryResult[]; compact?: boolean }) {
  if (results.length === 0) return <p className="text-xs text-(--color-ink-faint)">no candidates</p>;
  return (
    <div className="space-y-1.5">
      {results.slice(0, compact ? 3 : 6).map((r, i) => (
        <div key={r.agent_id} className="flex items-center justify-between gap-3 rounded-(--radius-sm) border border-(--color-line-soft) bg-(--color-surface-2) px-3 py-2">
          <div className="flex items-baseline gap-2">
            <span className="num mono text-xs text-(--color-ink-faint)">#{i + 1}</span>
            <span className="text-[13px] font-medium text-(--color-ink)">{r.display_name}</span>
            <span className="mono text-[11px] text-(--color-ink-faint)">{shortId(r.agent_id, 8)}</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="num mono text-sm">{r.score !== null ? r.score.toFixed(1) : "UNKNOWN"}</span>
            <DecisionBadge decision={r.decision} />
          </div>
        </div>
      ))}
    </div>
  );
}

function DecisionCard({ d, label, highlight = false }: { d: Delegation; label: string; highlight?: boolean }) {
  return (
    <div className={`rounded-(--radius-md) border px-4 py-3 ${highlight ? "border-(--color-accent)/40 bg-(--color-accent)/5" : "border-(--color-line-soft) bg-(--color-surface-2)"}`}>
      <p className="mb-1.5 text-[11px] tracking-wide text-(--color-ink-faint) uppercase">{label}</p>
      <div className="flex items-center gap-2">
        <DecisionBadge decision={d.decision} />
        <span className="text-xs text-(--color-ink-faint)">{humanize(d.status)}</span>
      </div>
      <ul className="mt-2 list-inside list-disc space-y-0.5 text-[11px] text-(--color-ink-dim)">
        {d.decision_detail?.reasons?.map((r) => (
          <li key={r.code}>{r.detail}</li>
        ))}
      </ul>
    </div>
  );
}

function humanize(s: string): string {
  return s.replace(/_/g, " ");
}

function useAgentList() {
  const [agents, setAgents] = useState<{ display_name: string; agent_id: string }[] | null>(null);
  useEffect(() => {
    let alive = true;
    api.listAgents()
      .then((r) => alive && setAgents(r.agents))
      .catch(() => alive && setAgents([]));
    return () => {
      alive = false;
    };
  }, []);
  return agents;
}
