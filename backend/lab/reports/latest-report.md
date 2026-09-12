# Adversarial Lab Report

*Generated 2026-09-12T00:51:28.669312+00:00*

| Attack | Expected | Result | Detail |
|---|---|---|---|
| Identity spoofing: fake agent claims trusted agent's identity | BLOCK | **BLOCKED/DETECTED** | passport documents are keyed by server-issued agent_id; forged submissions fail signature verification |
| Replay: resubmit identical evidence event | REJECT | **BLOCKED/DETECTED** | rejected: replay detected: nonce already used |
| Forged evidence: counterparty signature invalid | REJECT | **BLOCKED/DETECTED** | rejected: signature verification failed |
| Tampered event: DB-level UPDATE of historical evidence | DETECT | **BLOCKED/DETECTED** | append-only trigger blocked UPDATE at the database layer |
| Sybil farm: 1 actor → 8 mutually-endorsing agents | LIMITED REPUTATION INFLUENCE | **BLOCKED/DETECTED** | {"sybil_farm_attested_weight": 0.0, "honest_agent_attested_weight": 0.0, "same_owner_cap_applied": true, "young_issuer_damp_applied": true, "reciprocal_damp_applied": true} |
| Collusion: agents endorse each other in a cycle | DETECTED/REDUCED | **BLOCKED/DETECTED** | 4 reciprocal cycle(s); incident b41780579e734627bcff6f447911811a recorded |
| Reputation laundering: bad agent re-registers fresh | RISK FLAGGED | **BLOCKED/DETECTED** | lineage risk = high (['4 incident(s) in lineage', 'same owner resuming same capability set']); no auto-blacklist — re-verification policy applies |
| Model replacement: trusted agent swaps underlying model | TRUST RECALCULATED | **BLOCKED/DETECTED** | decision HUMAN_APPROVAL → REVERIFY; continuity factor 0.537; reverify=True |
| Capability escalation: low-risk agent requests financial capability | RE-EVALUATION REQUIRED | **BLOCKED/DETECTED** | escalation forces reverify=True; new-capability decision=REVERIFY |
| Owner transfer: reputation follows to a new owner | CONFIGURABLE INHERITANCE | **BLOCKED/DETECTED** | inherited with factor 0.472 (cap 0.75), reverify=True |
| Key compromise: revoke compromised key | REVOCATION PATH | **BLOCKED/DETECTED** | key agent-228e35db2b… revoked with reason + audit event; historical chain remains verifiable (1 events) |