# Architecture

## System view

```
                      ┌────────────────────────────────────────────┐
                      │              Frontend (React/TS)           │
                      │  overview · explorer · passport · graph    │
                      │  delegations · security · policy · audit   │
                      └──────────────────┬─────────────────────────┘
                                         │ /api/v1 (JSON, OpenAPI)
                      ┌──────────────────▼─────────────────────────┐
                      │         FastAPI modular monolith           │
                      │  auth · rate-limit · errors · logging      │
                      ├────────────────────────────────────────────┤
                      │              Service layer                 │
                      │  IdentityService   KeyService              │
                      │  EvidenceService   ReputationService       │
                      │  TrustDecisionService DelegationService    │
                      ├────────────────────────────────────────────┤
                      │           Domain layer (pure)              │
                      │  crypto · reputation · epochs ·            │
                      │  trust_graph · policy · interop            │
                      ├────────────────────────────────────────────┤
                      │        TrustConfig (all knobs)             │
                      └──────────────────┬─────────────────────────┘
                                         │ SQLAlchemy 2.0
                      ┌──────────────────▼─────────────────────────┐
                      │   SQLite (dev) / PostgreSQL (compose/prod) │
                      │   append-only triggers on evidence/audit   │
                      └────────────────────────────────────────────┘
```

Layering rule: **domain is pure** (no DB, no I/O) — fully unit-testable; services own persistence; API owns HTTP. Every trust number comes from `TrustConfig` (spec §68: no hardcoded policy).

## Core concepts

### Passport & identity (ADR-003)
`agents` row = persistent identity (UUID, owner org, status, risk class). `agent_versions` = immutable config snapshots (model, capabilities, tools, permissions) tied to epochs. Passports are platform-signed documents; contents are the only signed field set (whitelist canonicalization, ADR-004).

### Evidence ledger (ADR-005)
Per-agent chain: `event_hash = SHA256(canonical(body) ‖ prev_event_hash)`. Body includes the issuer's signature slot; counterparty submissions verify Ed25519 signatures over the canonical body before acceptance. Append-only enforced by DB triggers; corrections are new events referencing `corrective_of`. Visibility classes (public/org/private) gate API reads.

### Reputation (ADR-006)
Pure functions over evidence dicts. Per `(agent, capability)` vector over 8 dimensions. `w_i = quality · 2^(−age/half_life)`; anchored weighted mean with configurable prior; confidence = saturating `n_eff` curve × diversity discount (issuers, quality tiers, time span). Below `min_effective_evidence` → `UNKNOWN`.

### Trust epochs (ADR-007)
`update_agent(trigger=…)` closes epoch N, assesses continuity across 8 dimensions, computes the inheritance factor (weighted geometric mean, security multiplicative, owner-transfer capped), and writes the full assessment onto the epoch for explainability. `reverify` flag feeds the policy engine.

### Trust graph (ADR-008)
`trust_relationships` edges with capability + strength + confidence. Propagation: BFS, capability-matched, `max_depth=2`, per-hop discount γ=0.5, confidence ≤ weakest edge, weak edges ignored, `UNKNOWN` over fabrication. Damping: reciprocal 2-cycles ×0.5, same-owner caps, young-issuer damping. Detection: dense-cluster (k≥3, density ≥0.75) and cycle scan → Security Center incidents.

### Policy engine (spec §69)
`PolicyRule` = declarative matchers + outcome; DB rules + built-ins evaluated by priority; fixed pipeline: rules → UNKNOWN → thresholds → default ALLOW. Decisions always carry typed reasons.

## Data flow: the killer demo

```
discovery(vendor_negotiation)          ── rank by contextual trust
  → propose_delegation                 ── policy evaluation, decision recorded
  → complete_delegation                ── evidence appended (chain + signature)
  → update_agent(model_changed)        ── epoch 2, continuity 0.54, reverify=true
  → propose_delegation (same request)  ── REVERIFY (gated) with reasons
```

## Cross-cutting

- **Auth**: `X-API-Key` (admin for mutations; optional for reads) — constant-time compare. Production replaces with OAuth2 (ADR-011 path).
- **Observability** (spec §48): JSON structured logs, per-request duration header, health/ready endpoints, correlation-id header support; APScheduler background snapshots + security scans.
- **Interop** (ADR-011): A2A AgentCard (with `agentpassport` extension), `did:web` DID documents, VC-shaped attestation skeleton (honestly labeled), MCP JSON-RPC tools (`evaluate_trust`, `discover_agents`, `get_passport`).
- **Error envelope**: structured `{error, message}`; 500s never leak internals.

## Design decisions index

See [docs/adr/](adr/) ADR-001…012 for the full record (stack, identity, crypto, evidence, reputation, epochs, graph, design system, deployment, interop, privacy).
