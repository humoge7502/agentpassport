# ADR-006: Reputation Model — Multidimensional, Capability-Conditioned, With Confidence

**Status:** Accepted · **Date:** 2026-09-12

## Problem
`R(agent)` as a single 0–100 number is gameable and meaningless across contexts. We need `R(agent, capability, dimension, time)` with explicit uncertainty.

## Decision
**Representation.** For every `(agent, capability_type)` pair, a vector over dimensions
`reliability, security, accuracy, compliance, financial_integrity, task_performance, policy_compliance, delegation_reliability`.
Evidence `event_type`s map to dimensions with sign/magnitude (e.g. `task_completed`→+reliability/task_performance; `security_violation`→−security).

**Aggregation.** Weighted posterior mean over decayed, quality-weighted evidence:
- `w_i = quality_weight(tier_i) · exp(−ln2 · age_i / half_life)` (exponential decay, configurable half-life per dimension)
- `score = 100 · (w⁺ + prior_strength · prior_mean) / (w⁺ + w⁻ + prior_strength)` — a Bayesian-flavored weighted mean; `prior_strength` and `prior_mean` are config (default: neutral 0.5 prior, weak).
- Fresh agents with insufficient effective evidence report **`UNKNOWN`**, never a fabricated number.

**Confidence.** Effective sample size `n_eff = Σw_i` (in evidence-units) mapped through a saturating function
`confidence = 1 − 1/(1 + n_eff/n_half)` (n_half configurable, default ≈ 20), plus a **diversity discount**: confidence is multiplied by `f(sources, issuers, time_span)` so 200 events from one issuer in one hour do not fake certainty. Reported as a calibrated-feel percentage with the evidence count — never presented as more precision than the inputs justify.

**Capability conditioning.** Reputation is computed *per capability type*; an agent may be 95 on `translation` and 40 on `credential_management`. Global summary values are explicitly labeled aggregations, not the decision input.

**Selection among alternatives** (simple average / recency window / pure Bayesian / subjective-logic): the chosen composite was selected because (a) every parameter has an interpretable knob for policy owners, (b) adversarial behavior (burst-farming, self-report flooding) is damped by both decay and diversity discount, and (c) it degrades to UNKNOWN instead of pretending. Formal comparison and simulation results: `/research/reputation-prior-art.md`, `benchmarks/simulations/`.

## Tradeoffs
Not a closed-form Bayesian posterior (weights are heuristic); we compensate by testing calibration properties in the benchmark suite (BENCHMARKS.md) and documenting assumptions.
