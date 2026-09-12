# Contributing

## Ground rules

1. **No hardcoded policy.** Every threshold/weight lives in `TrustConfig` with a safe default. PRs adding magic numbers will be rejected.
2. **Evidence is append-only.** Never mutate historical rows; corrections are corrective events referencing `corrective_of`.
3. **Domain stays pure.** `app/domain/` has no DB/IO imports. Services own persistence; API owns HTTP.
4. **Fail closed, explain always.** New decision paths must return structured reasons, and `UNKNOWN` must remain `UNKNOWN` where evidence is insufficient.
5. **Claim discipline.** No "unhackable/Sybil-proof" language; update THREAT_MODEL.md alongside any security-relevant behavior change.

## Workflow

```bash
# 1. branch
git checkout -b feat/my-change

# 2. develop with tests (backend)
cd backend && pytest
python -m ruff check app tests lab benchmarks

# frontend changes
cd frontend && npx tsc --noEmit && npm run build

# 3. if trust behavior changed, also run:
python -m lab.attacks             # adversarial lab must stay 11/11
python -m benchmarks.agenttrustbench
```

## Commit & PR expectations

- Tests included; behavior fixes include a regression test.
- ADR required for: new dependency, schema change, any change to reputation math, epochs, propagation, or policy semantics.
- Docs synchronized (README/API/BENCHMARKS) in the same PR.
- PRs require: lint clean, 64+ tests green, lab green, frontend typecheck + build green (CI enforces).

## Security issues

Do not open public issues for vulnerabilities. See SECURITY.md "Reporting".

## License

Apache-2.0. By contributing you agree your contributions are licensed under it.
