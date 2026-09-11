# ADR-004: Cryptographic Algorithm & Key Management

**Status:** Accepted · **Date:** 2026-09-12

## Problem
All passports, evidence events, and trust relationships must be signable and verifiable; keys must support rotation, revocation, and compromise recovery.

## Options
1. **Ed25519** (via PyNaCl/libsodium) — fast, small signatures, deterministic, no nonce-failure class of bugs.
2. ECDSA P-256 — broader FIPS/ecosystem support, riskier to implement (nonce sensitivity).
3. RSA — obsolete size/perf for this use case.

## Decision
**Ed25519 (PyNaCl) + SHA-256 content hashes.**

- Canonical serialization: `json.dumps(..., sort_keys=True, separators=(",",":"))` over an explicit field whitelist (never the whole object) → signed bytes.
- `signing_keys` table: `key_id`, `agent_id` or `platform` scope, Ed25519 public key, `status` (active/retired/revoked), `created_at`, `retired_at`, `revoked_at`, `revocation_reason`.
- Rotation = generate new key, sign a *rotation evidence event* chaining old key_id → new key_id, retire old key. Old signatures stay verifiable via retired keys; trust weight of retired keys is preserved (rotations ≠ compromise).
- Revocation = status change + audit event; verification of events signed after revocation timestamp fails; the platform key signs the revocation attestation so third parties can verify it.
- Private keys live only in `APP_SECRET_KEYS_PATH` (file, 0600) or env for dev; **never** in the DB, never logged, never in API responses. Production deployments should inject from a secret manager.

## Tradeoffs
Ed25519 is not FIPS-validated; documented as a known limitation for regulated deployments. A key abstraction (`domain/crypto.py`) isolates the algorithm so P-256 can be added later.
