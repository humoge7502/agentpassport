# ADR-011: A2A / MCP Interoperability

**Status:** Accepted · **Date:** 2026-09-12

## Problem
AgentPassport must layer on top of — not replace — existing agent identity/communication standards, and avoid protocol lock-in.

## Decision
- **A2A:** expose each passport as an extended **AgentCard** (`/.well-known/agent-card.json` and `/api/v1/agents/{id}/agent-card`): standard A2A fields plus an `agentpassport` extension block (passport URL, trust summary, capability-conditioned scores, current epoch, verification manifest). Accept incoming A2A AgentCards with JWS signatures as *counterparty evidence* (`quality_tier=counterparty_signed`) after signature verification.
- **MCP:** publish an MCP server (`mcp/`) exposing trust tools (`evaluate_trust`, `discover_agents`, `get_passport`, `submit_evidence`) so any MCP client can make trust-gated tool decisions. MCP servers registering with a passport get their declared tools mirrored as capabilities (evidence: `capability_attested`).
- **Identity standards:** the passport's public-key section is stored in a **DID-compatible document** (`did:web` form: `did:web:{host}:agents:{id}`) with a verificationMethod mapping to the Ed25519 key — making passports resolvable by DID tooling without depending on a blockchain. Verification-material export in W3C VC shape is a documented extension point (`domain/interop/vc.py` skeleton + tests), not a V1 guarantee.

## Reasoning
Adoption path: platforms can consume the AgentCard with zero integration; DID/VC alignment keeps future cross-org federation open without forcing decentralized machinery into V1 (spec §84).
