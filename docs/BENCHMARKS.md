# AgentTrustBench — Benchmark Methodology & Results

Run: `cd backend && python -m benchmarks.agenttrustbench` · Results JSON: `benchmarks/results/latest-bench.json`

## What it is

A deterministic synthetic-scenario suite (seeded RNG, fixed dates) that measures whether the trust engine behaves *correctly under pressure* — not just whether code runs. Scenarios encode the behaviors the product promises (spec §51/§85/§86).

## Scenario → promise → measured metric

| Scenario | Promise under test | Metric (result) |
|---|---|---|
| `honest_agents` | honest performers get through; empty résumés don't | honest → `ALLOW`; 1-event newbie → `DENY` ✓ |
| `reputation_inflation` | self-report floods can't buy certainty | 300 self-reported events → confidence **0.308** < 30 quality events → **0.594** ✓ |
| `sybil_endorsement_boost` | endorsement rings gain little | 10/10 ring edges damped; 2-hop ring propagation **0.125** (0.5 damp × 0.5 damp × 0.5 γ-hop) ✓ |
| `model_change_trust_drop` | model swap gates trust | `ALLOW` → `REVERIFY` ✓ |
| `confidence_calibration` | confidence grows with evidence, monotonic, bounded | 0.236 → 0.556 → 0.744 (5 → 25 → 80 events) ✓ |
| `contextual_decay` | stale evidence fades | 400-day-old evidence → conf 0.0 (UNKNOWN); fresh → 0.527 ✓ |
| `decision_latency` | decisions are cheap | mean 10–16 ms, **p95 13–23 ms** across runs @ 120 evidence rows (warm SQLite) — well under the 50 ms gate ✓ |

## Methodology notes & honesty

- **Synthetic, deterministic** data only (fixed seeds/dates) — reproducible, no fielded claims.
- Metrics are behavioral checks (booleans/ratios) chosen to be **hard to game** (e.g., flood-vs-quality *confidence comparison*, not score levels an attacker could also hit).
- Decision-latency gate is a heuristic budget on dev hardware (CI runners vary); the structural property that matters is O(evidence-of-one-agent) scaling, verified by construction (evidence bucketed by agent, vector computed per capability, and reputation input bounded by an evidence age cutoff of 10 × the longest half-life — ancient rows never re-enter scoring or the latency budget).
- What the suite does **not** yet measure: long-horizon drift of the decay model, adversarially-adaptive attackers (attackers who model our damping), multi-capability portfolio effects. Tracked in RESEARCH.md future work.

## Adversarial lab companion

`python -m lab.attacks` executes 11 named attacks (spoofing, replay, forgery, tampering, Sybil farm, collusion ring, laundering, model replacement, capability escalation, owner transfer, key compromise) against fresh service instances and asserts expected defensive behavior: **11/11 blocked/detected**. Reports: `lab/reports/latest-report.md`.
