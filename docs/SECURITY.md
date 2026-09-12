# Security

AgentPassport treats security as the product. This document describes what is enforced, how keys are handled, and what is explicitly **out of scope or heuristic** — no "unhackable" claims (spec §87).

## Cryptography

- **Ed25519** (PyNaCl/libsodium) for all signatures; SHA-256 for hashes/chains (ADR-004).
- Canonical JSON signing over explicit field whitelists — no ambient-object signing.
- Signature verification failures reject evidence at ingestion; chain verification replays the full per-agent ledger (`/api/v1` verify path + service-level API).
- FIPS note: Ed25519 is not FIPS-validated; the crypto module is isolated for algorithm substitution in regulated deployments.

## Key custody

| Key | Dev/demo | Production requirement |
|---|---|---|
| Platform key | auto-generated at first boot into `APP_SECRET_KEYS_PATH` (file, 0600 on POSIX) | inject from a secret manager / KMS; mount read-only |
| Agent keys | server-managed, same store | **owner-held**: agent signs locally, platform only stores public keys (supported via externally-signed evidence) |
| Rotation | `POST /agents/{id}/keys/rotate` — old key retired, rotation event chained into evidence | same API |
| Revocation | `revoke_agent_key` + platform-signed attestation + audit event; post-revocation signatures fail verification **and revocation is enforced at ingestion** — evidence signed by a revoked key is rejected on submission, not merely flagged after the fact | same |
| Unregistered signers | externally-signed evidence from a key unknown to the platform is accepted only if the signature cryptographically verifies, and is downgraded to the `self_reported` tier (issuer `external`); an invalid signature from an unknown key is rejected outright | same |
| Compromise | revoke → re-verify path; historical chain remains verifiable via retired/revoked key material | same |

**Never**: private keys in the DB, in logs, in API responses, or committed to the repo (`.gitignore` blocks `keys/`).

## Application controls

- **Auth**: mutating endpoints require `X-API-Key` (constant-time compare). Change `APP_ADMIN_API_KEY` for anything shared; optional `APP_READ_API_KEY` locks reads.
- **Rate limiting**: per-client fixed window (default 120/min) on every request.
- **Input validation**: Pydantic schemas on every write path; enum-validated event types, quality tiers, visibility, triggers.
- **Replay defense**: nonce table (`replay_windows`) rejects duplicate evidence submissions; future-dated events beyond clock skew are rejected.
- **Append-only storage**: DB triggers block `UPDATE`/`DELETE` on `evidence_events` and `audit_events`; corrections are corrective events.
- **Error hygiene**: structured error envelope; 500s never leak stack traces, keys, or SQL.
- **Visibility enforcement** (ADR-012): evidence reads filter by public/org/private; private rows require the admin key.
- **Dependency posture**: minimal dependency set (FastAPI, SQLAlchemy, PyNaCl, …); pinned ranges; CI runs lint + tests; audit `pip list --outdated` / `uv pip list` periodically and `npm audit` for the frontend.

## Supply chain (spec §81)

No third-party "skill" is installed or executed in this repo. External guidance repositories were evaluated (`research/skill-evaluation-matrix.md`) and only their *principles* were adapted into our design system. Treat skill installation as code execution.

## Known limitations (read before trusting)

1. Single-operator trust root: the platform key is the anchor. If the platform is compromised, platform-verified evidence is forgeable. Mitigation path: threshold/HSM-backed keys, external auditors.
2. Sybil/collusion defenses are **heuristics** (caps, damping, clustering flags) — they raise attack cost; they do not make Sybil attacks impossible. See THREAT_MODEL.md.
3. Rate limiter is in-memory (per-process). Use a shared store (Redis) for multi-replica deployments.
4. SQLite dev mode: concurrent evidence appends are retried via `SAVEPOINT` (bounded retries with nonce registration), but SQLite remains single-writer; PostgreSQL is the supported multi-user backend.
5. Admin key auth is a development-grade control; production deployments should integrate OAuth 2.1 (MCP-compatible) before exposing beyond a trusted network.

## Reporting

Report vulnerabilities privately to the maintainers (see CONTRIBUTING.md). Please include reproduction steps and affected paths.
