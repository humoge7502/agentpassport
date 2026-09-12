# API Reference (v1)

Base: `http://localhost:8000/api/v1` · OpenAPI: `/api/openapi.json` · Docs UI: `/api/docs`

Auth: mutating endpoints require `X-API-Key: $ADMIN_API_KEY`. Reads are open in development (set `APP_READ_API_KEY` to lock). Rate limit: 120 req/min/client.

## Agents

| Method | Path | Notes |
|---|---|---|
| POST | `/agents` | register; returns signed passport (201) |
| GET | `/agents` | list; filters `capability`, `status`, `org`, `limit` |
| GET | `/agents/{id}` | passport document |
| GET | `/agents/{id}/passport` | **signed** passport `{passport, platform_key_id, signature}` |
| GET | `/agents/{id}/agent-card` | A2A AgentCard + `agentpassport` extension |
| GET | `/agents/{id}/did.json` | `did:web` DID document |
| GET | `/agents/{id}/attestation` | VC-shaped attestation (extension-point skeleton) |
| POST | `/agents/{id}/update` | lifecycle config change → new trust epoch. Body: `trigger` ∈ `model_changed\|owner_transferred\|capability_escalated\|tool_changed\|permission_changed` + fields. Returns continuity assessment + inherited reputation + `reverify_required` |
| POST | `/agents/{id}/lifecycle` | `{"action": "suspend"\|"revoke"\|"reactivate"}` |
| GET | `/agents/{id}/epochs` | epoch history with continuity + inheritance baselines |
| POST | `/agents/{id}/keys/rotate` | rotate signing key (old → retired, rotation evidence) |
| GET | `/agents/discover?capability=&risk_class=&transaction_value=&limit=` | capability discovery ranked by contextual trust |

## Trust

| Method | Path | Notes |
|---|---|---|
| POST | `/trust/evaluate` | **the** decision endpoint. Body: `{agent_id, capability, risk_class, transaction_value?, context?}` → `{decision, reasons[], score, confidence, policy_id}` — never a bare verdict |
| POST | `/trust/verify-signature` | verify Ed25519 signature over canonical JSON |
| GET | `/trust/graph` | nodes + edges for visualization |
| POST | `/trust/relationships` | record endorsement/delegation-grant edge |
| GET | `/trust/propagate?source=&target=&capability=` | contextual propagation → `KNOWN`/`UNKNOWN` with path |

## Evidence

| Method | Path | Notes |
|---|---|---|
| GET | `/agents/{id}/evidence` | visibility-enforced list (`visibility=public\|org\|private`; private needs admin key) |
| POST | `/evidence` | append signed event. Body: `{agent_id, event_type, capability?, task_class?, outcome?, context?, quality_tier?, visibility?, nonce?, corrective_of?, issuer_id?, external_signature?, external_public_key?}`. Event types: `task_completed, task_failed, policy_violation, security_violation, audit_passed, audit_failed, sla_met, sla_breached, transaction_completed, transaction_disputed, human_override, delegation_completed, delegation_failed, identity_verified, capability_attested, model_changed, tool_added, tool_removed, permission_changed, owner_changed, capability_added, capability_removed` |
| POST | `/agents/{id}/reputation/snapshot` | persist current vectors (trend history) |
| GET | `/agents/{id}/reputation?capability=&history=` | reputation vector(s) |

## Delegation

| Method | Path | Notes |
|---|---|---|
| POST | `/delegations/evaluate` | `{requester_agent_id, delegate_agent_id?, capability, risk_class, transaction_value?, discover?: bool}` — with `discover`, ranks candidates and delegates to the best eligible |
| POST | `/delegations/{id}/approve` | human approval gate (HUMAN_APPROVAL → approved) |
| POST | `/delegations/{id}/complete` | `{"outcome": "completed"\|"failed"}` → evidence appended |
| GET | `/delegations` | history with full decision records |

## Security, Policy, Audit, System

| Method | Path | Notes |
|---|---|---|
| GET | `/security/incidents` | sybil/collusion/forgery incidents |
| POST | `/security/scan` | run graph scan (reciprocal cycles, dense clusters, same-owner clusters) |
| POST | `/security/agents/{id}/lineage-check` | reputation-laundering risk assessment |
| GET/PUT/DELETE | `/policies[/{rule_id}]` | custom policy rules (matcher + outcome + priority) |
| GET | `/audit?entity_type=&entity_id=` | append-only audit trail (who/what/when/before/after/why) |
| GET/POST | `/mcp`, `/mcp/tools` | MCP-style JSON-RPC 2.0 tools (`tools/list`, `tools/call`: `evaluate_trust`, `discover_agents`, `get_passport`) |
| GET | `/health`, `/ready` (no prefix) | liveness / readiness |

## Error envelope

```json
{"error": "evidence_rejected", "message": "signature verification failed"}
```

`401` unauthorized · `404` not_found · `409` invalid_transition · `422` validation_error · `429` rate_limit_exceeded · `500` internal_error (no internals leaked).
