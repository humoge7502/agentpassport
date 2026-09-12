# Privacy

Principle: **auditability and privacy are in tension, and making everything public is not automatically more trustworthy** (spec §66). AgentPassport resolves this with visibility classes + aggregate disclosure, and documents what it does *not* solve.

## Visibility model (ADR-012)

Every evidence event and trust relationship carries `visibility`:

| Class | Who sees raw contents |
|---|---|
| `public` | any authenticated reader; passport exports |
| `org` | issuing/owning organization + platform |
| `private` *(default)* | issuer + platform only |

Enforced at the API layer (`GET /agents/{id}/evidence?visibility=…`) and covered by tests (private rows never appear in public/org reads without the admin key).

## What a public passport shows

Identity, capabilities, tools, permissions, risk class, epoch count, reputation vector + confidence, verification status, key material (public keys only).

## What it never shows publicly

Owner internals, delegation counterparties, incident details, evidence payloads, task content.

## Aggregate disclosure

Private evidence still *counts* toward reputation (otherwise scores lie), but public surfaces disclose only: evidence **count** and the **quality-tier mix** (`evidence_weight_summary`). Contents stay sealed. This is the honest V1 substitute for cryptographic selective disclosure.

## Data minimization

Schemas capture task *class* and outcome — not task content. Free-text `metadata` is discouraged by schema shape and stripped from public views.

## Personal data & deletion

AgentPassport stores machine identities, not personal data, by design. Organization names are operator-provided. Field-level redaction of personal data in metadata is supported via corrective events; evidence **hashes and chain structure are retained** (tombstoning) because rewriting history would break tamper-evidence for everyone. This is a deliberate, documented trade-off.

## Selective disclosure — future work, not faked

SD-JWT / SD-JWT-VC presentations, ZK proofs of reputation claims ("score ≥ X without revealing Y"), and per-counterparty disclosure policies are **designed for** (extension points in `domain/interop.py`) but **not implemented in V1**. We say so rather than pretending.
