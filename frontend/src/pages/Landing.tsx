/**
 * Public editorial layer — what AgentPassport is, why it exists, and proof
 * that the mechanisms work. The application console keeps its own dense
 * instrument-panel language (ADR-009); this page speaks the same token set
 * at editorial scale. All figures shown are real, from this repository's
 * test suite, adversarial lab, and benchmark (docs/BENCHMARKS.md).
 */

import { Link } from "react-router-dom";
import { useEffect, useState } from "react";
import { Reveal } from "../components/Reveal";
import { ThemeToggle } from "../components/ThemeToggle";

/* --- hero visual: an actual decision-record shape ------------------------- */

function DecisionReceipt() {
  return (
    <figure
      className="rounded-(--radius-lg) border border-(--color-line) bg-(--color-surface) shadow-[0_18px_50px_-24px_rgb(0_0_0/0.55)]"
      aria-label="Example trust decision record"
    >
      <figcaption className="flex items-center justify-between border-b border-(--color-line-soft) px-4 py-2.5">
        <span className="kicker">trust decision · req-8241</span>
        <span className="mono text-[11px] text-(--color-ink-faint)">epoch #1</span>
      </figcaption>
      <div className="space-y-3 px-4 py-3.5">
        <div className="flex items-baseline justify-between gap-3">
          <p className="mono text-[13px] text-(--color-ink)">vendor_negotiation</p>
          <p className="mono text-[11px] text-(--color-ink-dim)">$75,000 · high risk</p>
        </div>
        <div className="flex items-center justify-between gap-3 border-y border-(--color-line-soft) py-2.5">
          <span className="rounded-(--radius-sm) border border-(--color-allow)/30 bg-(--color-allow)/10 px-2 py-0.5 text-[12px] font-semibold tracking-wide text-(--color-allow)">
            ALLOW
          </span>
          <span className="num mono text-[12px] text-(--color-ink-dim)">
            score 82.4 · conf 0.74
          </span>
        </div>
        <ul className="space-y-1.5 text-[12px] text-(--color-ink-dim)">
          <li className="flex gap-2">
            <span className="text-(--color-allow)" aria-hidden>✓</span>
            <span>platform_verified record 60✓ / 2✗ on vendor_negotiation</span>
          </li>
          <li className="flex gap-2">
            <span className="text-(--color-allow)" aria-hidden>✓</span>
            <span>security 91 · no open incidents</span>
          </li>
          <li className="flex gap-2">
            <span className="text-(--color-allow)" aria-hidden>✓</span>
            <span>policy <span className="mono">vendor_negotiation.high</span>: score ≥ 80, conf ≥ 0.70</span>
          </li>
        </ul>
      </div>
    </figure>
  );
}

/** Animated per-agent hash chain — the product's core data structure, drawn. */
function ChainStrip() {
  const hashes = ["9f3a…c21e", "04bd…77a9", "e512…0f83", "c9d0…4417", "7a6f…b2e0"];
  return (
    <div aria-hidden className="mt-4">
      <svg viewBox="0 0 420 74" className="w-full" role="presentation">
        {hashes.map((h, i) => {
          const x = 8 + i * 84;
          return (
            <g key={h}>
              <line
                x1={x + 66} y1={30} x2={x + 84} y2={30}
                stroke="var(--color-line)" strokeWidth="1.5"
                className={i < hashes.length - 1 ? "chain-flow" : undefined}
              />
              <rect
                x={x} y={12} width={66} height={36} rx={7}
                fill="var(--color-surface-2)" stroke="var(--color-line)"
              />
              <text x={x + 33} y={27} textAnchor="middle" fontSize="8.5"
                fill="var(--color-ink-faint)" fontFamily="var(--font-mono)">
                seq 04{i + 1}
              </text>
              <text x={x + 33} y={40} textAnchor="middle" fontSize="8.5"
                fill="var(--color-ink-dim)" fontFamily="var(--font-mono)">
                {h}
              </text>
            </g>
          );
        })}
        <text x={8} y={66} fontSize="9" fill="var(--color-ink-faint)" fontFamily="var(--font-mono)">
          append-only evidence ledger · Ed25519-signed · hash-chained per agent
        </text>
      </svg>
    </div>
  );
}

/* --- sections -------------------------------------------------------------- */

const PROBLEMS = [
  ["a", "Static API keys can't say “trusted for translation, not for payments.” Access is binary; risk isn't."],
  ["b", "An agent's track record lives in operational logs nobody verifies — performance is indistinguishable from marketing."],
  ["c", "A model swap at 3 p.m. silently inherits the trust earned by the model it replaced at 9 a.m."],
];

const STEPS = [
  {
    n: "01", title: "Evidence",
    lead: "Every outcome, signed and chained.",
    body: "Counterparty-signed attestations land in an append-only, per-agent hash chain — enforced twice, by database triggers and by chain verification. Tampering breaks the chain; a revoked signing key is rejected at the door.",
    note: "Ed25519 · canonical JSON · SHA-256",
  },
  {
    n: "02", title: "Reputation",
    lead: "Per capability, with a memory that fades.",
    body: "Scores are capability-conditioned, quality-tiered, and decay on a half-life. Confidence pools across total evidence mass and issuer diversity — a flood of self-reports cannot buy the certainty that a few signed attestations earn.",
    note: "n_eff pooling · diversity discount · 60-day half-life",
  },
  {
    n: "03", title: "Decision",
    lead: "Every gate shows its work.",
    body: "The policy engine answers with ALLOW, DENY, REVERIFY, or HUMAN_APPROVAL — always with cited reasons. UNKNOWN is a first-class answer when evidence is thin, and identity changes force trust to be re-earned.",
    note: "risk-tiered floors · confidence gates · reason trail",
  },
];

const OUTCOMES: Array<[string, string, string]> = [
  ["ALLOW", "allow", "The record clears every floor for this capability and risk class."],
  ["REVERIFY", "condition", "Identity changed — model, owner, tooling. Trust must be re-earned, not inherited."],
  ["HUMAN_APPROVAL", "condition", "High value meets thin confidence. A person decides, with the evidence in front of them."],
  ["DENY", "deny", "A floor failed and the reason is cited — never a bare refusal."],
];

const AUDIENCES: Array<[string, string]> = [
  ["Platform teams", "Gate what agents may do on your infrastructure, with decisions you can audit after the fact."],
  ["Agent marketplaces", "Rank sellers by evidence-backed track records instead of unverifiable vendor claims."],
  ["Regulated industries", "Model or owner changes force re-verification; high-value actions can require a human."],
];

function SectionHead({ id, n, title, lead }: { id: string; n: string; title: string; lead: string }) {
  return (
    <Reveal className="max-w-2xl">
      <p className="kicker">{n} — {title}</p>
      <h2 id={id} className="display mt-3 text-[clamp(1.7rem,3.4vw,2.6rem)] text-(--color-ink)">
        {lead}
      </h2>
    </Reveal>
  );
}

/* --- page ------------------------------------------------------------------ */

export function Landing() {
  const [up, setUp] = useState<boolean | null>(null);
  useEffect(() => {
    let alive = true;
    fetch("/health")
      .then((r) => r.ok)
      .then((ok) => alive && setUp(ok))
      .catch(() => alive && setUp(false));
    return () => { alive = false; };
  }, []);

  return (
    <div className="min-h-screen">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:absolute focus:top-2 focus:left-2 focus:z-50 focus:rounded focus:bg-(--color-accent) focus:px-3 focus:py-1 focus:text-white"
      >
        Skip to content
      </a>

      {/* top bar — static; the page scrolls naturally */}
      <header className="border-b border-(--color-line-soft)">
        <div className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-5 py-3.5">
          <p className="flex items-center gap-2.5">
            <span className="flex h-8 w-8 items-center justify-center rounded-(--radius-sm) border border-(--color-accent-dim) bg-(--color-accent-dim)/30" aria-hidden>
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="var(--color-accent)" strokeWidth="2">
                <path d="M12 3l8 4v5c0 5-3.5 8-8 9-4.5-1-8-4-8-9V7l8-4Z" />
              </svg>
            </span>
            <span className="text-[14px] font-semibold tracking-tight">AgentPassport</span>
            <span className="kicker hidden sm:inline">trust infrastructure</span>
          </p>
          <div className="flex items-center gap-3">
            <Link to="/overview" className="link-draw text-[13px] font-medium text-(--color-ink)">
              Open console
            </Link>
            <ThemeToggle />
          </div>
        </div>
      </header>

      <main id="main">
        {/* HERO */}
        <section className="border-b border-(--color-line-soft)" aria-labelledby="hero-h">
          <div className="mx-auto grid max-w-6xl grid-cols-1 items-center gap-10 px-5 py-16 md:py-24 lg:grid-cols-12">
            <div className="lg:col-span-7">
              <p className="kicker">continuous trust infrastructure for autonomous agents</p>
              <h1 id="hero-h" className="display mt-4 text-[clamp(2.5rem,5.4vw,4.4rem)] text-(--color-ink)">
                Every agent has a record. Decisions should read it.
              </h1>
              <p className="mt-5 max-w-xl text-[15px] leading-relaxed text-(--color-ink-dim)">
                AgentPassport gives AI agents a persistent, portable identity, a
                tamper-evident evidence ledger, and capability-conditioned
                reputation — so “can this agent do X, right now?” has a
                citable answer instead of a vibe.
              </p>
              <div className="mt-7 flex flex-wrap items-center gap-3">
                <Link
                  to="/overview"
                  className="rounded-(--radius-sm) bg-(--color-accent) px-4 py-2.5 text-[13px] font-semibold text-(--color-bg) transition-transform duration-(--duration-fast) hover:-translate-y-px active:translate-y-0"
                >
                  Open the console
                </Link>
                <Link
                  to="/demo"
                  className="rounded-(--radius-sm) border border-(--color-line) px-4 py-2.5 text-[13px] font-medium text-(--color-ink) transition-colors duration-(--duration-fast) hover:bg-(--color-surface-2)"
                >
                  Watch it decide <span aria-hidden>→</span>
                </Link>
              </div>
              <p className="mono mt-5 text-[11px] text-(--color-ink-faint)">
                runs locally · synthetic demo data · every number on this page is from this build
              </p>
            </div>
            <div className="lg:col-span-5">
              <Reveal delay={120}>
                <DecisionReceipt />
                <ChainStrip />
              </Reveal>
            </div>
          </div>
        </section>

        {/* PROOF STRIP */}
        <section className="border-b border-(--color-line-soft) bg-(--color-surface)" aria-label="Verified by this build">
          <div className="mx-auto max-w-6xl px-5 py-8">
            <Reveal>
              <div className="grid grid-cols-2 gap-x-6 gap-y-5 sm:grid-cols-4">
                {[
                  ["11/11", "adversarial attacks blocked or detected"],
                  ["7/7", "benchmark scenarios behave correctly"],
                  ["< 25 ms", "p95 decision latency at 120 evidence rows"],
                  ["78", "tests green on this build"],
                ].map(([v, k]) => (
                  <div key={k}>
                    <p className="num mono text-2xl font-semibold tracking-tight text-(--color-ink)">{v}</p>
                    <p className="mt-1 text-[12px] leading-snug text-(--color-ink-faint)">{k}</p>
                  </div>
                ))}
              </div>
              <p className="mt-5 border-t border-(--color-line-soft) pt-3 text-[11px] leading-relaxed text-(--color-ink-faint)">
                Measured by the in-repository adversarial lab and AgentTrustBench.
                These are simulations of mechanism behavior — not fielded security,
                and no claim here is “unhackable” or “Sybil-proof.” That honesty is
                the product.
              </p>
            </Reveal>
          </div>
        </section>

        {/* 01 PROBLEM */}
        <section className="border-b border-(--color-line-soft)" aria-labelledby="problem-h">
          <div className="mx-auto grid max-w-6xl grid-cols-1 gap-10 px-5 py-16 md:py-20 lg:grid-cols-12">
            <div className="lg:col-span-6">
              <SectionHead id="problem-h" n="01" title="the problem" lead="Agents stopped being functions. They have histories — and histories get rewritten." />
            </div>
            <div className="lg:col-span-5 lg:col-start-8">
              <ul className="space-y-5">
                {PROBLEMS.map(([i, text], idx) => (
                  <Reveal as="li" key={i} delay={idx * 70} className="flex gap-4 border-b border-(--color-line-soft) pb-5">
                    <span className="mono text-[12px] text-(--color-accent)">({i})</span>
                    <p className="text-[14px] leading-relaxed text-(--color-ink-dim)">{text}</p>
                  </Reveal>
                ))}
              </ul>
            </div>
          </div>
        </section>

        {/* 02 HOW IT WORKS */}
        <section className="border-b border-(--color-line-soft) bg-(--color-surface)" aria-labelledby="how-h">
          <div className="mx-auto max-w-6xl px-5 py-16 md:py-20">
            <SectionHead id="how-h" n="02" title="the mechanism" lead="Evidence becomes reputation. Reputation gates decisions. Decisions explain themselves." />
            <ol className="mt-10 grid grid-cols-1 gap-px overflow-hidden rounded-(--radius-lg) border border-(--color-line-soft) bg-(--color-line-soft) md:grid-cols-3">
              {STEPS.map((s, idx) => (
                <Reveal as="li" key={s.n} delay={idx * 90} className="flex flex-col bg-(--color-bg) p-6">
                  <span className="num mono text-[13px] font-semibold text-(--color-accent)">{s.n}</span>
                  <h3 className="mt-3 text-[17px] font-semibold tracking-tight text-(--color-ink)">{s.title}</h3>
                  <p className="mt-1 text-[13px] font-medium text-(--color-ink-dim)">{s.lead}</p>
                  <p className="mt-2.5 text-[13px] leading-relaxed text-(--color-ink-faint)">{s.body}</p>
                  <p className="mono mt-auto pt-4 text-[10px] tracking-wide text-(--color-ink-faint) uppercase">
                    {s.note}
                  </p>
                </Reveal>
              ))}
            </ol>
          </div>
        </section>

        {/* 03 OUTCOMES */}
        <section className="border-b border-(--color-line-soft)" aria-labelledby="outcomes-h">
          <div className="mx-auto grid max-w-6xl grid-cols-1 gap-10 px-5 py-16 md:py-20 lg:grid-cols-12">
            <div className="lg:col-span-5">
              <SectionHead id="outcomes-h" n="03" title="the four answers" lead="Never a bare ALLOW or DENY." />
              <Reveal delay={120}>
                <p className="mt-4 max-w-md text-[14px] leading-relaxed text-(--color-ink-dim)">
                  Every decision carries its evidence, its policy citations, and
                  its uncertainty. When the record is insufficient, the system
                  says UNKNOWN — it does not guess.
                </p>
              </Reveal>
            </div>
            <dl className="lg:col-span-6 lg:col-start-7">
              {OUTCOMES.map(([name, tone, text], idx) => (
                <Reveal key={name} delay={idx * 60} className="border-b border-(--color-line-soft)">
                  <div className="flex flex-col gap-1.5 py-4 sm:flex-row sm:items-baseline sm:gap-5">
                    <dt className="w-36 shrink-0">
                      <span className={`mono text-[12px] font-semibold ${
                        tone === "allow" ? "text-(--color-allow)"
                          : tone === "deny" ? "text-(--color-deny)"
                          : "text-(--color-condition)"
                      }`}>
                        {name}
                      </span>
                    </dt>
                    <dd className="text-[13px] leading-relaxed text-(--color-ink-dim)">{text}</dd>
                  </div>
                </Reveal>
              ))}
            </dl>
          </div>
        </section>

        {/* 04 AUDIENCES */}
        <section className="border-b border-(--color-line-soft) bg-(--color-surface)" aria-labelledby="who-h">
          <div className="mx-auto max-w-6xl px-5 py-16 md:py-20">
            <SectionHead id="who-h" n="04" title="who this is for" lead="Built for people who have to answer for what an agent did." />
            <dl className="mt-8 divide-y divide-(--color-line-soft) border-y border-(--color-line-soft)">
              {AUDIENCES.map(([who, why], idx) => (
                <Reveal key={who} delay={idx * 70} className="grid grid-cols-1 gap-1.5 py-5 sm:grid-cols-12 sm:gap-6">
                  <dt className="text-[15px] font-semibold tracking-tight text-(--color-ink) sm:col-span-4">
                    {who}
                  </dt>
                  <dd className="text-[13.5px] leading-relaxed text-(--color-ink-dim) sm:col-span-8">
                    {why}
                  </dd>
                </Reveal>
              ))}
            </dl>
          </div>
        </section>

        {/* FINAL CTA */}
        <section aria-labelledby="cta-h">
          <div className="mx-auto max-w-6xl px-5 py-20 text-center md:py-28">
            <Reveal>
              <h2 id="cta-h" className="display mx-auto max-w-3xl text-[clamp(1.9rem,4vw,3.1rem)] text-(--color-ink)">
                Watch a model change gate a $75,000 transaction.
              </h2>
              <p className="mx-auto mt-4 max-w-xl text-[14px] leading-relaxed text-(--color-ink-dim)">
                The killer demo runs a real delegation against the seeded
                ledger — before and after the agent's model changes underneath it.
              </p>
              <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
                <Link
                  to="/demo"
                  className="rounded-(--radius-sm) bg-(--color-accent) px-5 py-3 text-[13px] font-semibold text-(--color-bg) transition-transform duration-(--duration-fast) hover:-translate-y-px active:translate-y-0"
                >
                  Run the killer demo
                </Link>
                <Link
                  to="/overview"
                  className="rounded-(--radius-sm) border border-(--color-line) px-5 py-3 text-[13px] font-medium text-(--color-ink) transition-colors duration-(--duration-fast) hover:bg-(--color-surface-2)"
                >
                  Explore the console
                </Link>
              </div>
            </Reveal>
          </div>
        </section>
      </main>

      {/* FOOTER */}
      <footer className="border-t border-(--color-line-soft) bg-(--color-surface)">
        <div className="mx-auto max-w-6xl px-5 py-12">
          <div className="grid grid-cols-2 gap-8 sm:grid-cols-12">
            <div className="col-span-2 sm:col-span-5">
              <p className="flex items-center gap-2.5">
                <span className="flex h-7 w-7 items-center justify-center rounded-(--radius-sm) border border-(--color-accent-dim) bg-(--color-accent-dim)/30" aria-hidden>
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--color-accent)" strokeWidth="2">
                    <path d="M12 3l8 4v5c0 5-3.5 8-8 9-4.5-1-8-4-8-9V7l8-4Z" />
                  </svg>
                </span>
                <span className="text-[13px] font-semibold tracking-tight">AgentPassport</span>
              </p>
              <p className="mt-3 max-w-xs text-[12.5px] leading-relaxed text-(--color-ink-faint)">
                Continuous, portable identity and evidence-backed,
                capability-conditioned reputation for autonomous AI agents.
              </p>
              <p className="mono mt-4 flex items-center gap-1.5 text-[11px] text-(--color-ink-faint)">
                <span
                  className={`h-1.5 w-1.5 rounded-full ${up === null ? "pulse-soft bg-(--color-condition)" : up ? "bg-(--color-allow)" : "bg-(--color-deny)"}`}
                  aria-hidden
                />
                {up === null ? "checking api…" : up ? "api connected" : "api unreachable"}
              </p>
            </div>
            <nav className="sm:col-span-3" aria-label="Product">
              <p className="kicker">product</p>
              <ul className="mt-3 space-y-2 text-[13px]">
                <li><Link className="link-draw text-(--color-ink-dim) hover:text-(--color-ink)" to="/overview">Console</Link></li>
                <li><Link className="link-draw text-(--color-ink-dim) hover:text-(--color-ink)" to="/demo">Killer demo</Link></li>
                <li><Link className="link-draw text-(--color-ink-dim) hover:text-(--color-ink)" to="/graph">Trust graph</Link></li>
                <li><Link className="link-draw text-(--color-ink-dim) hover:text-(--color-ink)" to="/agents">Agent explorer</Link></li>
              </ul>
            </nav>
            <nav className="sm:col-span-4" aria-label="Governance">
              <p className="kicker">governance</p>
              <ul className="mt-3 space-y-2 text-[13px]">
                <li><Link className="link-draw text-(--color-ink-dim) hover:text-(--color-ink)" to="/security">Security center</Link></li>
                <li><Link className="link-draw text-(--color-ink-dim) hover:text-(--color-ink)" to="/policies">Policy center</Link></li>
                <li><Link className="link-draw text-(--color-ink-dim) hover:text-(--color-ink)" to="/audit">Audit center</Link></li>
                <li><Link className="link-draw text-(--color-ink-dim) hover:text-(--color-ink)" to="/delegations">Delegation center</Link></li>
              </ul>
            </nav>
          </div>
          <div className="mt-10 flex flex-col gap-2 border-t border-(--color-line-soft) pt-4 sm:flex-row sm:items-center sm:justify-between">
            <p className="mono text-[11px] text-(--color-ink-faint)">
              v1.0.0 · demo environment · synthetic data
            </p>
            <p className="mono text-[11px] text-(--color-ink-faint)">
              © 2026 AgentPassport · WCAG 2.2 AA target · respects reduced motion
            </p>
          </div>
        </div>
      </footer>
    </div>
  );
}
