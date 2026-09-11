# Reputation & Trust Systems — Prior Art and Algorithm Selection

*Sources: established literature (noted inline). Fresh 2026 web research covered standards (see standards-analysis.md); the algorithmic literature below is stable and cited to primary work. Where we rely on it, we mark ADOPT / ADAPT / REJECT.*

## 1. EigenTrust (Kamvar, Schlosser, Garcia-Molina, WWW 2003)

**Core:** global trust = power iteration of normalized local trust: `T_i = Σ_j c_ij · T_j` with `c_ij = s_ij / Σ_k s_ik`; pre-trusted distribution `P` breaks rank sinks.
**Why useful:** consensus-style aggregation and the pre-trusted anchor idea (our platform-verified tier plays that role).
**Weakness:** assumes mostly-honest majority; no uncertainty; transitive by construction — dangerous for us.
**Call: ADAPT** the anchored-aggregation idea; **REJECT** full transitive iteration (ADR-008 uses bounded, capability-matched, discounted propagation instead).

## 2. Beta Reputation (Jøsang & Ismail, 2006) & Subjective Logic

**Core:** feedback as beta evidence `(r, s)`; belief `b = r/(r+s+u)` etc.; **opinion ω = (b, d, u, a)** explicitly carries *uncertainty*; opinion operators (fusion, discounting) combine evidence and third-party recommendations.
**Why useful:** the `(belief, disbelief, uncertainty)` triple is exactly our score/confidence split; **discounting** `(A ⊗ B)` is the honest way to propagate trust through a chain — propagated belief inherits the recommender's uncertainty (our propagation confidence ≤ weakest edge mirrors this).
**Weakness:** operators are order-sensitive and can be opinionated for sparse data.
**Call: ADAPT** — uncertainty representation and discounting semantics; not the full opinion algebra.

## 3. PageRank-family / SybilRank (Cao et al., IWQoS 2013) & SybilGuard (Yu et al., 2006)

**Core:** trust ranking via random-walk mixing from trusted anchors; SybilRank bounds Sybil influence by their edge MIX with non-Sybil region; SybilGuard assumes fast-mixing social graphs.
**Why useful:** validates our anchor-and-cap approach: influence grows with verified connectivity, dense reciprocal clusters concentrate rank and are detectable.
**Weakness:** assumes fast-mixing honest region — we cannot assume that for agent endorsement graphs, so we use it as a *signal generator* (flags, influence caps), not an oracle.
**Call: ADAPT** as heuristics (k-core density, reciprocal cycles, ownership clustering).

## 4. Sybil attack baseline (Douceur, IPTPS 2002)

Formalized: without a centralized identity authority, Sybil resistance is impossible. **We are that authority** (issuing orgs authenticated, platform key chain) — this is the load-bearing assumption, documented in THREAT_MODEL.md. Claim discipline: inside our deployment we bound Sybil cost; cross-org federation dilutes it (future work).

## 5. Time decay

**Exponential decay** `exp(−ln2·t/h)` chosen over (a) hard windows (evidence cliff — bad for stability), (b) linear decay (tail never dies, stale evidence lingers), (c) power-law (heavy head; one old success can dominate). Half-life is a per-dimension policy knob. Edge cases tested: burst evidence, steady drip, stale-good + recent-bad (recent must dominate), all in `tests/test_reputation.py`.

## 6. Confidence / uncertainty quantification

- **Wilson score interval** (Wilson 1927): good for bounded proportions; we use its *spirit* (interval widens at low n) via the saturating `confidence = 1 − 1/(1 + n_eff/n_half)` on effective (quality+decay weighted) sample size.
- **Hoeffding bound**: `ε = sqrt(ln(2/δ)/2n)` justifies the shape (confidence grows √n) — our saturating form is the display-friendly monotone equivalent; we do not claim the bound's guarantees since weights violate IID assumptions.
- **Diversity discount** (ours, adapted from recommendation-system robustness work): confidence multiplied by `g(#issuers, #sources, time-span)` so single-issuer floods cannot fake certainty. Honest: heuristic, tested for monotonicity and attack resistance in simulations, not a proven estimator.

## 7. Capability-based authorization

**Macaroons** (Birgisson et al., NDSS 2014) / **Biscotti**/**caveats**: delegable credentials with attenuating caveats — informs our delegation model (delegations carry capability + constraints + expiry) and contextual propagation (attenuation on every hop).

## 8. AI-agent trust prior art (2024–2026 landscape)

Agent marketplaces rank by ratings (self-reported, Sybil-prone); A2A leaves card signing optional; no deployed system in our search couples **capability-conditioned multidimensional reputation + evidence-quality tiers + trust epochs with continuity-based inheritance + contextual propagation**. The *composite* is our differentiator; the ingredients are drawn from the literature above. (Detailed matrix in docs/prior-art-matrix.md.)

## Recommended composite (implemented in ADR-006/007/008)

```
w_i      = quality_weight(tier_i) · exp(−ln2 · age_i / half_life_dim)          # evidence weight
score    = 100 · (w⁺ + s·p) / (w⁺ + w⁻ + s)                                    # anchored weighted mean
n_eff    = Σ w_i ;  confidence = (1 − 1/(1 + n_eff/n_half)) · diversity(sources, issuers, span)
inherit  = Π_k continuity_k^(weight_k)        # geometric mean over continuity dims (per-trigger weights)
propagate(A→C, cap) = edge_strength · γ^hop  iff capability matches, bounded depth, confidence ≤ min edge
```

Every constant is a config knob with a safe default; behavior is verified in `benchmarks/simulations/` against adversarial scenarios rather than asserted.
