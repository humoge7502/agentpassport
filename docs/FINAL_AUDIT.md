# FINAL AUDIT

*Independent audit pass, 2026-09-12; second hardening pass, 2026-09-13. Posture: "the implementation is broken until proven otherwise." Every claim below was verified by execution on this machine, not assumed.*

## Verification evidence

| Check | Command | Result |
|---|---|---|
| Backend tests | `pytest tests/` | **78 passed** (unit + service + API integration + interop + iteration-2 regressions) |
| Lint | `ruff check app tests lab benchmarks` | **clean** |
| Adversarial lab | `python -m lab.attacks` | **11/11 attacks blocked/detected** |
| AgentTrustBench | `python -m benchmarks.agenttrustbench` | **7/7 scenarios pass** (decision p95 ≈ 13–23 ms across runs) |
| Frontend typecheck + build | `tsc --noEmit && vite build` | **clean** (69 KB gzip) |
| Migration | `alembic upgrade head` on fresh SQLite | **clean** |
| Full-stack smoke | API + UI live, seeded, pages exercised in-browser | **working** |
| Visual acceptance | independent judge over 9 rendered pages | **9/9 pass** (1 cosmetic nit, fixed) |
| Mobile layout | CDP-measured `scrollWidth` == 390 on all 9 routes @ 390×844 | **pass** (1 real defect found & fixed, below) |

## Critical issues

**None open.** (Two were found and fixed during the build: the API `get_db` dependency used a separate engine from the service registry — unified; evidence visibility clamp let anonymous readers see org-class rows — tightened to public-only with a regression test.)

## High issues

**None open.** (Fixed during build: SQLite dropped timezone info, silently breaking signed evidence hashes after reload — fixed with a UTC-preserving column type + hash-chain tests; BFS propagation recorded nodes beyond `max_depth` — fixed + test.)

## Medium issues (accepted, documented)

1. **In-memory rate limiter** — per-process only; multi-replica deployments need a shared store (documented in DEPLOYMENT.md).
2. **Admin-key auth** is development-grade — production path documented (OAuth 2.1, ADR-011); acceptable for the current deployment scope.
3. **In-process scheduler** — background jobs won't scale horizontally; upgrade path documented.
4. **Sybil/collusion defenses are heuristics** — cost-raising, not proof; extensively disclosed in THREAT_MODEL.md and configurable.

## Low issues

1. Passport tab capitalization inconsistency — **fixed** after visual review.
2. `docker` build paths untested in CI beyond config validation (no Docker-in-CI execution); compose file validated locally.
3. Frontend bundle ships Inter/JetBrains Mono via system fallbacks (no webfont download dependency) — intentional, zero external requests.

## Known limitations (product-honest)

- Single-operator trust root; platform compromise out of scope for V1 (THREAT_MODEL.md).
- No live-agent behavior monitoring — the platform attests to *records*, not live intent (prompt-injection boundary documented).
- `did:web` export is fully functional; **VC export is an honestly-labeled skeleton**, not a spec-compliant credential.
- Reputation confidence is a calibrated-feel heuristic (n_eff saturating × diversity), not a proven estimator; benchmark probes monotonicity/boundedness rather than claiming statistical guarantees.

## Resolved during development (selected)

- Alembic autogen imported custom type without its module import — fixed migration.
- `find_reciprocal_cycles` double-counted pairs — fixed + test.
- Policy `max_confidence` matcher missing — added (high-value human-approval rule).
- Evidence visibility matrix — tightened + parametrized regression test.
- Owner transfer to a non-existent org hit FK constraint — auto-ensure org + lab attack now passes.

## Second pass (2026-09-13): hardening iteration — findings & resolutions

1. **Evidence signed by a revoked key was verifiable at ingestion** (high) — ingestion now checks key status against the registry *before* signature verification and rejects revoked-key evidence (`test_revoked_key_rejected_at_ingestion`).
2. **Unregistered external signer handling was inconsistent** (medium) — externally-signed evidence with an unknown key now requires a valid signature and is honestly downgraded to `self_reported`/`external`; invalid signatures from unknown keys are rejected (`test_unregistered_external_key_rejected_without_valid_signature`).
3. **Overall confidence used a min-across-dimensions aggregate** (high, design) — one thin dimension capped the certainty of a large behavioral base. Replaced with pooled confidence: total evidence mass × issuer/tier/time-span diversity discount, in the domain model, the decision-path view, and the UI (`overall()` + tests; seed re-tuned so the killer demo still shows ALLOW → REVERIFY across the model change).
4. **Concurrent evidence appends could lose writes under contention** (medium) — append now retries inside a `SAVEPOINT` with bounded retries and nonce registration (`test_append_race_retries`).
5. **Unbounded growth paths** (low) — replay-nonce window pruned opportunistically; rate-limiter client tracker bounded (10k) with expired-window eviction; reputation input bounded by an evidence age cutoff (10 × longest half-life).
6. **Overview page horizontally overflowed on mobile** (medium, visual) — implicit single-column grid tracks sized to the embedded table's min-content (page rendered 512 px wide at a 390 px viewport). All responsive grids now declare explicit `grid-cols-1` (`minmax(0,1fr)`) tracks; verified by CDP measurement across all 9 routes.
7. **WCAG contrast** — `--color-ink-faint` raised to 4.5:1 on the surface background.

## Verdict

All critical and high issues resolved; medium issues are documented deployment boundaries rather than defects. The repository satisfies the release gate: tests, lint, adversarial lab, benchmarks, build, migration, visual acceptance, and end-to-end demo all verified green.
