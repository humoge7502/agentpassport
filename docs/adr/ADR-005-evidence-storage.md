# ADR-005: Evidence Storage — Append-Only Hash-Chained Ledger

**Status:** Accepted · **Date:** 2026-09-12

## Problem
Evidence must be tamper-evident, immutable, provenance-carrying, and efficient enough to aggregate per agent (reputation inputs).

## Options
1. Plain append-only table + DB constraints
2. **Per-agent hash chain + signatures + DB constraints**
3. Merkle tree / blockchain — premature decentralization (rejected for V1 per spec §84)

## Decision
**Option 2.** Each `evidence_events` row contains:
`event_id (uuid), agent_id, seq (per-agent monotonic), event_type, capability, task_class, outcome, context (json), issuer_type, issuer_id, signing_key_id, signature, payload_hash, prev_event_hash, event_hash, quality_tier, metadata (json), created_at`.

- `event_hash = SHA-256(canonical(event) || prev_event_hash)` — per-agent chain; any mutation breaks the chain, `POST /agents/{id}/evidence/verify` replays it.
- Signature covers the canonical event body (including `prev_event_hash`), made by the issuer's Ed25519 key (agent self-report, counterparty, or platform).
- DB enforces append-only: `ON CONFLICT` guard on `(agent_id, seq)`, UPDATE/DELETE blocked by trigger; corrections are *new corrective events* referencing `event_id` (ADR: data integrity, spec §65).
- `quality_tier` ∈ {self_reported, counterparty_signed, platform_verified, independent_audit, cryptographic} — weights in config (ADR-006), never silently upgraded.
- Indexes: `(agent_id, seq)` unique, `(agent_id, event_type, created_at)`, `(capability, created_at)`.

## Tradeoffs
Full-chain verification is O(n) per agent; acceptable (evidence is per-agent, thousands not billions). Merkle anchoring of chain heads is the designated future extension point.
