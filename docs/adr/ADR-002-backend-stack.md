# ADR-002: Backend Stack

**Status:** Accepted · **Date:** 2026-09-12

## Problem
The backend must implement: Ed25519 signing/verification, an append-only hash-chained evidence ledger, statistical reputation math (decay, weighting, uncertainty), graph analysis (Sybil/collusion heuristics), a policy engine, and a typed REST API. It must also host reproducible simulations and benchmarks.

## Options
1. **Python 3.13 + FastAPI + Pydantic v2 + SQLAlchemy 2.0**
2. Node/TypeScript (NestJS/Fastify) — one language across stack, but weaker stack for statistical/graph work.
3. Go — excellent performance, more ceremony for the analytics-heavy domain layer.

## Decision
**Option 1: Python 3.13 + FastAPI + Pydantic v2 + SQLAlchemy 2.0.**

## Reasoning
- Reputation math, decay, confidence intervals, simulations, and benchmark scenarios are the intellectual core — Python is the strongest ecosystem for this and lets the benchmark suite run in-process against the same domain code.
- Pydantic v2 gives strict, typed request/response schemas and doubles as JSON Schema export for API docs.
- FastAPI gives async performance adequate for the decision path (p95 target < 50 ms for trust evaluation on warm data, see BENCHMARKS.md).

## Tradeoffs / Consequences
- Two languages across the stack (Python + TypeScript); mitigated by an OpenAPI-generated typed client for the frontend.
- GIL limits CPU-parallel request scaling; acceptable at this scale (decision path is O(evidence for one agent)), and the design isolates heavy batch computation (reputation snapshots, simulations) in offline jobs.
