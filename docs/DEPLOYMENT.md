# Deployment

## Topology (ADR-010)

Modular monolith: `web (nginx static + proxy)` → `api (uvicorn ×2 workers)` → `PostgreSQL 16` (+ `appkeys` volume for server-managed keys). Background jobs run in-process (APScheduler) — swap for a worker container at scale.

## Docker Compose (recommended)

```bash
cp .env.example .env            # set APP_ADMIN_API_KEY!
docker compose up --build -d
docker compose exec api alembic upgrade head
docker compose exec api python -m app.demo.seed   # optional demo data
# UI: http://localhost:8080 · API: http://localhost:8000
```

## Configuration (all via env, prefix `APP_`)

| Variable | Meaning | Production guidance |
|---|---|---|
| `DATABASE_URL` | SQLite (dev) or PostgreSQL DSN | always PostgreSQL |
| `ADMIN_API_KEY` | mutation auth | **required change**; 32+ random chars |
| `READ_API_KEY` | optional read auth | set for non-public deployments |
| `SECRET_KEYS_PATH` | server-managed Ed25519 key dir | mount a secret; read-only |
| `CORS_ORIGINS` | allowed origins | lock to your UI origin |
| `PUBLIC_BASE_URL` | used in DID docs / agent cards | your public URL |
| `RATE_LIMIT_PER_MINUTE` | per-client limit | tune per load |
| `JOBS_ENABLED`, `JOBS_INTERVAL_SECONDS` | background snapshots/scans | fine defaults |

## Production checklist

- [ ] `APP_ADMIN_API_KEY` changed; `APP_READ_API_KEY` set if API is not public
- [ ] PostgreSQL with TLS + backups (evidence ledger and audit are the crown jewels — PITR recommended)
- [ ] Platform key injected from secret manager (not baked into images)
- [ ] `APP_ENV=production`
- [ ] Migrations applied (`alembic upgrade head`) before rollout
- [ ] Reverse proxy TLS termination; `CORS_ORIGINS` locked
- [ ] `/ready` wired into orchestration health checks
- [ ] Log aggregation pointed at the JSON stdout stream
- [ ] Dependency audit scheduled (`pip audit`, `npm audit`)

## Scaling notes

- API is stateless except the in-memory rate limiter — for multi-replica, back the limiter with Redis or deploy a gateway limiter.
- Decision path is O(evidence of one agent); reputation snapshots are the batch-heavy path — move `jobs.py` to a worker container before scaling replicas.
- Evidence chain verification is O(n) per agent (thousands of events is fine); verify on demand, not per request.

## Backup & recovery

`pg_dump` covers all state. Server-managed private keys live in the `appkeys` volume — **back them up securely or plan re-issuance** (rotation + re-verification). Recovery = restore DB + keys, `alembic upgrade head`, restart; evidence chains verify byte-identical (UTCDateTime canonicalization guarantees hash stability across restore).
