# ADR-010: Deployment Architecture

**Status:** Accepted · **Date:** 2026-09-12

## Problem
Local dev must be one command; production should be simple, observable, and not prematurely distributed.

## Decision
**Modular monolith.** One FastAPI service + one PostgreSQL + (optional) Redis for rate limiting/job queue.

- **Dev (zero external deps):** `DATABASE_URL=sqlite:///./agentpassport.db` — full feature set including crypto; `uvicorn app.main:app --reload`.
- **Dev/Prod parity:** `docker compose up` → `api` (uvicorn, 2 workers), `db` (postgres:16, healthcheck-gated), optional `redis`. Migrations (Alembic) run via `docker compose exec api alembic upgrade head`; seed demo via `python -m app.demo.seed`.
- Frontend: static build (Vite) served by any CDN/nginx; in compose, an `nginx` profile serving `dist/` and proxying `/api`.
- Config via env (`pydantic-settings`), `.env.example` documents every variable with safe placeholders. Secrets (platform signing key) injected via `APP_SECRET_KEYS_PATH`, never baked into images.
- Background jobs (collusion scans, reputation snapshots) run as APScheduler in-process with a `jobs.enabled` flag; documented upgrade path to a worker container.

## Tradeoffs
In-process scheduler limits horizontal scale; fine for the target deployment and swappable via the job interface.
