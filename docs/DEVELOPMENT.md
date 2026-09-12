# Development

## Prerequisites

Python 3.12+ (3.13 recommended), Node 20+, [uv](https://docs.astral.sh/uv/) (optional but fast). Docker optional (compose path).

## Setup

```bash
# backend
cd backend
uv venv .venv && uv pip install -e ".[dev]"
./.venv/Scripts/python -m app.demo.seed        # Windows
# ./.venv/bin/python -m app.demo.seed          # macOS/Linux

# run API
./.venv/Scripts/python -m uvicorn app.main:app --reload

# frontend (second terminal)
cd frontend && npm install && npm run dev
```

- API: http://localhost:8000 · OpenAPI: `/api/docs`
- UI: http://localhost:5173

Admin key for mutations (dev): `dev-admin-key-change-me` (header `X-API-Key`).

## Test pyramid (spec §49)

| Layer | Command | What it covers |
|---|---|---|
| Unit (domain) | `pytest tests/test_crypto.py tests/test_reputation.py tests/test_epochs.py tests/test_trust_graph.py tests/test_policy.py` | pure trust-engine math, edge cases, adversarial inputs |
| Service integration | `pytest tests/test_evidence_service.py` | chaining, signing, replay, append-only triggers, visibility |
| API integration | `pytest tests/test_api.py` | full workflows incl. the killer-demo path, authz, a2a card |
| Adversarial lab | `python -m lab.attacks` | 11 attack simulations → report in `lab/reports/` |
| Benchmarks | `python -m benchmarks.agenttrustbench` | scenario metrics + decision latency |

Target: `pytest` all green (64 tests), lab 11/11, bench scenarios passing.

## Quality gates

```bash
./.venv/Scripts/python -m ruff check app tests lab benchmarks   # lint
npx tsc --noEmit                                                 # frontend types (in frontend/)
npm run build                                                    # frontend prod build
```

## Layout notes

- `app/domain/` is **pure** — no DB imports. Keep it that way; tests depend on it.
- `TrustConfig` (`app/domain/trust_config.py`) is the single home for every tunable. Adding policy constants anywhere else is a review-blocking bug.
- Evidence events are **append-only**: never mutate rows; append corrective events.
- The API uses route-order-sensitive literal paths before `/{agent_id}` — keep `/discover` registered first.

## Debugging tips

- Reset dev DB: delete `backend/agentpassport.db*` and re-run the seed.
- Logs are JSON on stdout (`agentpassport` logger); request lines include `duration_ms`.
- Alembic: `alembic revision --autogenerate -m "..."` then `alembic upgrade head` (uses `APP_DATABASE_URL`).

## Conventions

- Typed Python (Pydantic v2 schemas at the boundary), TypeScript strict for the frontend.
- Comments state constraints, not narration.
- Every new trust-behavior change ships with: tests + a THREAT_MODEL/benchmarks note when adversarial.
