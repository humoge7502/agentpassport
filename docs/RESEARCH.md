# Research Index & Prior-Art Matrix

Research artifacts live in [`/research`](../research/):

| File | Content |
|---|---|
| [standards-analysis.md](../research/standards-analysis.md) | A2A/AgentCard (JWS, RFC 8785), MCP OAuth 2.1, DID/VC 2.0, SD-JWT, SPIFFE — adopt/integrate/notes |
| [reputation-prior-art.md](../research/reputation-prior-art.md) | EigenTrust, Jøsang beta reputation & subjective logic, SybilRank/SybilGuard, decay models, Wilson/Hoeffding confidence, capability tokens — with ADOPT/ADAPT/REJECT calls |
| [design-research-acmvit.md](../research/design-research-acmvit.md) | ACM-VIT critical analysis + modern dashboard references → token recommendations |
| [skill-evaluation-matrix.md](../research/skill-evaluation-matrix.md) | impeccable / taste-skill / emilkowalski/skills / VoltAgent evaluations + distilled principles |

## Prior-art matrix (condensed)

Goal: identify genuinely differentiated mechanisms; **not** legal advice.

| Reference (approx. date) | Concept | Overlap | Difference | Potentially novel in AgentPassport |
|---|---|---|---|---|
| EigenTrust (2003) | transitive global trust via iteration | reputation aggregation | we reject blind transitivity; bounded capability-matched propagation with UNKNOWN | — |
| Jøsang beta reputation / subjective logic (2006-2016) | uncertainty-carrying opinions, discounting | score+confidence, propagation discount | we add evidence *quality tiers* and diversity discount | composite: quality tiers × decay × diversity on capability-conditioned vectors |
| SybilGuard/SybilRank (2006-2013) | graph-based Sybil ranking | cluster detection | identity-issued graph (we are the authority); influence caps not bans | same-owner capping + young-issuer damping as policy knobs |
| Douceur (2002) | Sybil attack impossibility | — | we instantiate the required centralized authority | — |
| Macaroons/Biscotti (2014+) | delegable attenuated capabilities | delegation carries constraints | applied to *agent* delegation with trust-epoch gating | delegation decisions with explainable policy evaluation |
| A2A AgentCard (2024-2026) | agent discovery metadata, optional JWS signing | identity card concept | signing optional there; mandatory + reputation extension here | AgentPassport extension block + trust-conditioned ranking |
| Agent marketplaces w/ ratings (2024-2026) | user ratings for agents | "reputation" name | ratings are self-reported & global; ours is evidence-tiered, capability-conditioned, decayed, epoch-gated | trust epochs + continuity-based inheritance |
| Patent-adjacent: dynamic trust/workload identity systems (e.g., SPIFFE attestation flows) | platform-attested identity | platform-verified evidence tier | we layer behavioral reputation atop identity | epoch-continuity inheritance model |

**Claimed differentiation is the *composite***: capability-conditioned multidimensional reputation + evidence-quality tiers + confidence-with-diversity + trust epochs with measured continuity inheritance + contextual (non-transitive) propagation + policy-gated delegation — implemented and adversarially tested as a coherent system. Individual ingredients are drawn from cited prior art. No patent/novelty claims are made; this matrix is engineering due diligence only.

## Open research questions (tracked)

1. Calibration of confidence outputs under adversarial evidence distributions (bench probes monotonicity; formal calibration audits are future work).
2. Decay half-life selection per capability class (currently a uniform 60-day default knob).
3. Cross-org federation without a single trust root (VC/SD-JWT path in ADR-011/012).
4. Behavior-continuity measurement quality (currently volume/mix/outcome-shift proxies).

## Implemented vs. hypothesized vs. future

- **Implemented + tested**: evidence quality weighting, decay, diversity-discounted confidence, epoch continuity/inheritance, propagation discounting, Sybil/collusion heuristics, policy engine (see tests + benchmarks).
- **Hypothesized (documented assumptions)**: damping parameters' real-world adequacy; collusion cluster thresholds.
- **Future research**: formal calibration audits, adaptive-adversary simulations, federated trust anchors.
