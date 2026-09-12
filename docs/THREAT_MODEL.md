# Threat Model

Scope: the AgentPassport platform, its APIs, the evidence ledger, the reputation/trust engine, and the delegation flow. Assumption (Douceur 2002): **without a centralized identity authority, Sybil resistance is impossible — we are that authority.** Everything below is evaluated against that assumption; claims are scoped and honest (spec §87).

## Assets

1. **Integrity of the evidence ledger** (history must be tamper-evident)
2. **Meaningfulness of reputation** (scores must reflect behavior, not manipulation)
3. **Correctness of trust decisions** (gates must fail closed)
4. **Key material** (platform + agent signing keys)
5. **Privacy of private/org evidence** (ADR-012)

## Adversaries & defenses

| Threat | Vector | Defense | Status |
|---|---|---|---|
| Identity spoofing | fake agent claims a trusted identity | server-issued `agent_id`; forged submissions fail signature verification; passports are platform-signed | **BLOCKED** (lab ✓) |
| Credential/key theft | stolen Ed25519 key | key rotation + revocation; revocation attestation; post-revocation signatures fail | **PATH EXISTS** (lab ✓) |
| Replay | resubmit captured evidence | per-agent nonce window; duplicates rejected | **BLOCKED** (lab ✓) |
| Event forgery | fake counterparty evidence | Ed25519 verification over canonical body at ingestion | **BLOCKED** (lab ✓) |
| Event tampering | direct DB writes to history | append-only DB triggers + hash-chain verification (defense in depth) | **BLOCKED** (lab ✓) |
| Sybil farm | 1 actor mints N mutually-endorsing agents | identity roots (authenticated orgs); same-owner endorsement caps; young-issuer damping; reciprocal-cycle damping ×0.5; dense-cluster flags | **COST RAISED, not impossible** — heuristic (lab ✓ flags) |
| Collusion | circular endorsement rings | 2-cycle damping; dense-subgraph detection (k≥3, density ≥0.75) → incidents + reduced influence | **DETECTED/REDUCED** (lab ✓) |
| Reputation laundering | bad actor re-registers fresh | lineage risk heuristic (incidents, key overlap, owner+capability overlap) → flag for re-verification; **no auto-blacklist** (legitimate rotation preserved) | **FLAGGED** (lab ✓) |
| Model replacement abuse | swap model, keep old trust | trust epochs: continuity assessment (model dim = 0 cross-family), geometric-mean inheritance, `reverify` gate in policy | **TRUST RECALCULATED** (lab ✓) |
| Capability escalation | low-risk agent grabs high-risk capability | escalation forces reverify; new capability has no reputation → UNKNOWN → gated | **RE-EVALUATION FORCED** (lab ✓) |
| Owner transfer | reputation follows to a new owner | ownership continuity 0 → inheritance capped at 0.75; reverify forced | **CONFIGURABLE** (lab ✓) |
| Evidence flooding | 100s of self-reports to inflate confidence | quality-tier weights + diversity discount (issuers × tiers × time span) | **DAMPED** (bench ✓) |
| API abuse / DoS | request floods | rate limiting (per-client window); O(evidence-of-one-agent) decision path (p95 ≈ 11 ms at 120 events) | partial — Redis-backed limiter for multi-replica |
| Confused deputy / delegation abuse | malicious requester picks a high-trust delegate for a different purpose | delegation evaluated against delegate+capability+risk+value; decisions recorded with reasons; capability-matched propagation prevents cross-capability leakage | mitigated |
| Prompt injection *(out of scope, documented)* | agents are LLM systems; AgentPassport evaluates *records*, not live agent behavior | boundary: the platform attests to evidence about behavior, never to live intent; integrators must gate actual tool execution themselves | **documented boundary** |
| Platform compromise | attacker controls the trust root | out of scope for V1 single-operator design; mitigations: HSM/threshold keys, external auditors, cross-org federation (future) | **known limitation** |
| Privacy breach | private evidence exposure | visibility classes enforced at API layer; private rows need admin key; aggregated disclosure only (ADR-012) | enforced by tests ✓ |

## Trust-propagation honesty

`propagate_trust` answers "does A trust C for X?" — capability-matched, depth-bounded, discounted, confidence-capped by the weakest edge, and returns `UNKNOWN` when evidence is insufficient. Cross-capability leakage is tested (A⇒B procurement, B⇒C translation ⇏ A⇒C procurement).

## What we do NOT claim

- Not **Sybil-proof** — heuristics raise cost; determined adversaries with diverse authenticated orgs can still farm.
- Not **fraud-proof** — the platform key anchors platform-verified evidence.
- Reputation scores are **decision inputs with uncertainty**, not ground truth.
- The lab and bench results are **simulations**; they demonstrate mechanism behavior, not fielded security.

## Open problems → future work

Post-quantum signatures (hybrid schemes), threshold platform keys, cross-org federation with decentralized attestations (VC/SD-JWT selective disclosure), formal calibration audits of confidence outputs, behavioral anomaly detection on evidence streams.
