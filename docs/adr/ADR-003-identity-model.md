# ADR-003: Identity Model

**Status:** Accepted · **Date:** 2026-09-12

## Problem
Agents need persistent machine identity that survives restarts and deployments, while explicitly decoupling *identity continuity* from *behavioral trust continuity*.

## Decision
- An **Agent Passport** is the root record: `agent_id` (UUIDv7), `owner_org_id`, `display_name`, `status` (draft/active/suspended/revoked), `risk_class` (low/medium/high/critical), `identity_version` (monotonic), timestamps.
- Passport **contents** (model, capabilities, permissions, tools) are versioned snapshots: `agent_versions` rows, each linked to the `trust_epoch` it started. The current passport view = latest version + live status.
- **Capabilities** are typed entries (`capability_type`, `risk_class`, `constraints`) — not free strings. Reputation, policy, and discovery all key off capability types.
- Identity persistence is keyed by `agent_id` + owner root. Identity continuity ≠ trust continuity: any change to model/tools/capabilities/permissions/owner opens a new trust epoch (ADR-007) and triggers re-evaluation.

## Reasoning
UUIDv7 gives time-ordered ids (index-friendly). Versioned snapshots make "what did we trust at time T" a queryable fact, required for audits and reputation inheritance.

## Tradeoffs
Snapshot-on-every-change grows rows; mitigated because changes are infrequent relative to evidence events, and snapshots are small.
