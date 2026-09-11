# ADR-008: Trust Graph & Contextual Propagation

**Status:** Accepted · **Date:** 2026-09-12

## Problem
Trust relationships (delegations, endorsements, org ownership, evidence issuance) form a graph. Naive transitive closure ("friend-of-friend is trusted") is exactly the vulnerability Sybils exploit.

## Decision
- Graph nodes: agents, organizations, capability types (for capability-matched edges). Edges: `trust_relationships` (issuer→subject, capability, weight, evidence_ref), `delegations`, org ownership, issuance.
- **Propagation is bounded, capability-matched, and discounted:** to answer "does A trust C for capability X", walk edges whose capability *matches* X (or is strictly broader), with multiplicative discount `edge_strength × γ^hop` (γ default 0.5, max_depth default 2), and produce either a propagated trust estimate **with confidence ≤ the weakest edge's confidence**, or `UNKNOWN`. Unknown stays unknown — no fallback to popular guess.
- **Sybil resistance (defense-in-depth, honest about limits):** (1) identity roots — issuing orgs are authenticated; (2) ownership clustering — endorsements between agents sharing an owner/root are capped; (3) endorsement topology — dense reciprocal clusters (fast cycle detection + k-core density heuristics) get an *influence cap*, not auto-ban; (4) new-agent damping — endorsements from very young issuers carry reduced weight; (5) rate/velocity signals surface in the Security Center. Claim discipline: this raises attack cost; it is **not** Sybil-proof (see THREAT_MODEL.md).
- **Collusion detection:** reciprocal-cycle and dense-subgraph analysis over the endorsement graph runs as a periodic job; flagged clusters reduce endorsement influence via the cap mechanism and raise a security signal.
- **Reputation laundering:** agent lineage (prior_ids, re-registration links from key reuse or owner+model+capability overlap) feeds a *lineage risk* input; a fresh identity with high-overlap lineage to a failed agent gets flagged for re-verification, while genuinely new agents are not blacklisted.

## Tradeoffs
Heuristic graph analytics (not a formal Sybil-resistant protocol); all thresholds configurable and all flags explainable in the UI.
