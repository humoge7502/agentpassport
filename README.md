# AgentPassport

**Continuous, portable identity + evidence-backed, capability-conditioned reputation for autonomous AI agents.**

> An AI agent should possess a persistent machine identity, a verifiable capability profile, and a reputation derived from cryptographically verifiable behavior rather than self-reported ratings.

The critical differentiator: **when an agent changes — its model, tools, permissions, owner, or behavior — trust must dynamically change**, rather than blindly inheriting historical reputation.

The system answers one question:

> *Is this the same sufficiently-trusted agent I trusted before, and is it sufficiently trustworthy for **this** task, capability, context, risk level, and time?*

---

## What it is

AgentPassport is **trust decision infrastructure** — not an identity directory:

| Layer | What it does |
|---|---|
| **Identity** | Persistent agent passports with Ed25519 signing keys, rotation, revocation |
| **Evidence** | Append-only, per-agent hash-chained, signed event ledger with quality tiers |
| **Reputation** | Multidimensional, capability-conditioned scores with explicit confidence and time decay |
| **Trust Epochs** | Model/tool/capability/owner changes close epochs; reputation is *re-inherited* by measured continuity, never copied blindly |
| **Trust Graph** | Contextual (non-transitive) propagation, Sybil/collusion defenses, laundering flags |
| **Policy Engine** | Configurable rules → `ALLOW / DENY / HUMAN_APPROVAL / REVERIFY / UNKNOWN`, always with reasons |
| **Discovery & Delegation** | Capability-based discovery ranked by contextual trust; gated delegation decisions |
| **Dashboard** | Enterprise-grade operator console for all of the above |

## Quick start

```bash
# 1. Backend (SQLite — zero external deps)
cd backend
uv venv .venv && uv pip install -e ".[dev]"     # or: pip install -e ".[dev]"
python -m app.demo.seed                          # deterministic demo world
python -m uvicorn app.main:app --reload          # API on :8000

# 2. Frontend
cd ../frontend
npm install
npm run dev                                      # UI on :5173 (proxies /api)
```

Or with Docker (PostgreSQL + API + web):

```bash
cp .env.example .env
docker compose up --build
# API on :8000 · UI on :8080
```

Then open **http://localhost:5173**. The landing page tells the product story with real numbers from this build; the **console** (sidebar or “Open console”) is the instrument panel. Try the **Killer Demo** page: it walks the flagship scenario — *delegation succeeds → the delegate swaps its model → the same request is visibly gated*. Dark and light themes are both fully designed (toggle in the top bar).

## Create an agent & make a trust decision

```bash
KEY='dev-admin-key-change-me'

# register an agent (returns a signed passport)
curl -X POST http://localhost:8000/api/v1/agents \
  -H "X-API-Key: $KEY" -H "Content-Type: application/json" \
  -d '{"owner_org_id":"org-acme","display_name":"MyAgent",
       "capabilities":["translation"],"model_id":"atlas-4"}'

# record signed evidence (platform-signs; counterparty signatures also supported)
curl -X POST http://localhost:8000/api/v1/evidence \
  -H "X-API-Key: $KEY" -H "Content-Type: application/json" \
  -d '{"agent_id":"<id>","event_type":"task_completed","capability":"translation",
       "quality_tier":"platform_verified","nonce":"n-1"}'

# the central question
curl -X POST http://localhost:8000/api/v1/trust/evaluate \
  -H "Content-Type: application/json" \
  -d '{"agent_id":"<id>","capability":"translation","risk_class":"medium"}'
```

The decision always carries **structured reasons** — never a bare `DENY`.

## How reputation works

`R(agent, capability, dimension, time)` — never a single global number:

- **Evidence quality tiers** (self-reported 0.3× → independent audit 1.0×) weight every event.
- **Exponential time decay** (60-day default half-life) makes recent behavior matter more.
- **Confidence** saturates with effective evidence *and* is discounted for low diversity — 300 self-reports from one issuer cannot fake certainty.
- **Insufficient evidence → `UNKNOWN`**, never a fabricated score.

## How trust decisions work

```
request(agent, capability, risk, value)
  → policy rules (DB rules + built-ins: security floor, thresholds by risk class,
    high-value human approval, epoch reverify gate)
  → UNKNOWN handling (deny-with-reason by default)
  → score + confidence gates per risk class
  → decision + explicit, explainable reasons
```

## Agent evolution

Any material change (model, tools, capabilities, permissions, owner) **closes the current trust epoch** and opens a new one. Continuity is measured per dimension (identity, ownership, model, capabilities, tools, permissions, security, behavior); inheritance is a weighted geometric mean — a collapsed dimension dominates, and owner transfers are hard-capped. Below the threshold, decisions flip to `REVERIFY`.

## How to run everything

```bash
cd backend
pytest                      # 64 unit + integration tests
python -m lab.attacks       # adversarial lab: 11 attacks → expect 11 blocked/detected
python -m benchmarks.agenttrustbench   # AgentTrustBench scenarios + latency
```

## Repository layout

```
backend/
  app/
    domain/        # pure trust engine: crypto, reputation, epochs, graph, policy
    models.py      # SQLAlchemy schema (append-only guards incl.)
    services_*     # identity, evidence, decision, delegation services
    api_*.py       # FastAPI routers (agents, trust, delegation, security, mcp)
    demo/          # deterministic demo seed (killer-demo scenario)
  tests/           # 64 tests
  lab/             # adversarial security lab (11 attack simulations)
  benchmarks/      # AgentTrustBench
  migrations/      # Alembic
frontend/          # React + TS + Tailwind v4 dashboard
research/          # standards analysis, prior art, design research, skill matrix
docs/              # ARCHITECTURE, SECURITY, THREAT_MODEL, ADRs, …
deploy/            # Dockerfiles, nginx
```

## Documentation

[ARCHITECTURE](docs/ARCHITECTURE.md) · [SECURITY](docs/SECURITY.md) · [THREAT_MODEL](docs/THREAT_MODEL.md) · [API](docs/API.md) · [DEVELOPMENT](docs/DEVELOPMENT.md) · [DEPLOYMENT](docs/DEPLOYMENT.md) · [BENCHMARKS](docs/BENCHMARKS.md) · [PRIVACY](docs/PRIVACY.md) · [DESIGN_SYSTEM](docs/DESIGN_SYSTEM.md) · [RESEARCH](research/) · [ADRs](docs/adr/)

## Status & honest limits

V1 is a working centralized system. It is **not** Sybil-proof, not blockchain-based (deliberately — extension points documented), and the Sybil/collusion defenses are heuristics with disclosed limits. See [THREAT_MODEL](docs/THREAT_MODEL.md) and [FINAL_AUDIT](docs/FINAL_AUDIT.md).

License: Apache-2.0. All demo data is synthetic.
