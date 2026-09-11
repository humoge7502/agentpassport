# ADR-012: Privacy Architecture

**Status:** Accepted · **Date:** 2026-09-12

## Problem
Auditability and privacy are in tension. Making all evidence public is *not* automatically more trustworthy (spec §66) — it leaks business relationships, task content, and failure patterns to competitors and attackers.

## Decision
**Three visibility classes on every evidence event and relationship, enforced at the API layer (default `private`):**
- `public` — visible to any authenticated reader and on public passport exports (aggregates only by default).
- `org` — visible within the issuing/owning organization.
- `private` — visible to issuer + platform only.

**Rules:**
1. Reputation *scores and confidence* derived from private evidence are publishable as aggregates (evidence *count and class mix* disclosed, contents not) — the ZK/selective-disclosure upgrade path (SD-JWT / VC presentations) is documented as future work, not faked in V1.
2. Evidence payloads are minimized by schema: task *class*, outcome, not raw task content. Free-text metadata is discouraged by schema and stripped from public views.
3. Passport public view exposes: identity, capabilities, risk class, epoch count, reputation vector + confidence, verification status. It does **not** expose: owner internals, delegation counterparties, incident details, or evidence payloads.
4. Audit events record actor *roles/ids*, not credentials or secrets; log scrubbing for key material in structured logs.
5. GDPR-style deletion applies to *personal* data in metadata via field-level redaction events; evidence hashes and chain integrity are retained (tombstoning) — documented in PRIVACY.md.

## Tradeoffs
Private evidence weakens public verifiability by design; the compensate is signed aggregates + disclosed evidence-class mix. Honest limitation, documented.
