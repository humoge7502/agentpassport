# Standards & Protocol Analysis (2026)

*Researched 2026-09-12 via live web search. Conclusion up front: AgentPassport should be a **trust/evidence/reputation layer above** existing identity and communication standards — A2A for discovery/interchange, MCP for tool-context integration, OAuth 2.1 for authorization transport, DID-compatible key documents for portability. Do not reinvent authentication or transport.*

## 1. A2A (Agent2Agent, Linux Foundation / a2aproject)

**What it is today.** Open protocol for independent agents to discover each other and delegate tasks. The **AgentCard** is a JSON metadata document (identity, capabilities/skills, service endpoint, security requirements) published by an A2A server, conventionally at `/.well-known/agent-card.json` (an IETF Internet-Draft, `draft-aevum-agentcard`, proposes AgentCard as a framework-neutral identity format).

**Signing.** The spec defines a JWS-based AgentCard signing scheme: signatures computed over **RFC 8785 (JCS) canonicalized** AgentCard JSON, base64url protected header + signature, recommended practice **Ed25519 keys with `kid` resolvable via a JWKS endpoint**. **Signing is optional by spec** — an acknowledged trust gap ("Your Agent Card is naked"; "Agent Card Trust Is Optional by Spec").

**Adopt / Integrate (ADR-011):**
- AgentPassport exposes each passport as an AgentCard with an `agentpassport` extension block; JWS signing of our card follows the spec's scheme (Ed25519, `kid`→JWKS), so A2A-native clients can verify us.
- Inbound signed AgentCards are accepted as **counterparty evidence** after JWS verification over RFC 8785 canonical form — the trust layer the spec leaves optional.

## 2. MCP (Model Context Protocol)

**What it is today.** Protocol for connecting models to tools/resources. Remote HTTP servers **must use OAuth 2.1** (PKCE mandatory) as authorization framework; servers act as OAuth **protected resources** identified via Protected Resource Metadata (PRM) / `WWW-Authenticate` challenges. Current spec lines: 2025-11-25 (authorization), 2026-07-28 docs.

**Integrate:** AgentPassport's own API uses OAuth2 bearer tokens / API keys with the same OAuth 2.1 discipline (scoped tokens, no ambient authority). We publish an MCP server exposing trust tools (`evaluate_trust`, `discover_agents`, `get_passport`, `submit_evidence`) so any MCP client can gate tool use on trust decisions. MCP servers registering with passports have declared tools mirrored as capabilities.

## 3. W3C DID & Verifiable Credentials 2.0

**What they are.** DID: portable, cryptographically verifiable identifiers with DID Documents (verificationMethod, key agreement). VC 2.0: signed credential data model, increasingly `@context`-stable, SD-JWT-VC profile emerging for selective disclosure.

**Adopt (partially):** Passports export a **`did:web`-compatible document** (`did:web:{host}:agents:{id}`) whose verificationMethod maps to the passport's Ed25519 key — resolvable by DID tooling without blockchain. A **VC-shaped attestation export** is a documented extension point (skeleton + tests), not a V1 guarantee (ADR-011).

## 4. OAuth 2.1 / OIDC / JWT / SD-JWT

**Adopt:** OAuth 2.1 is the transport-level auth for our API. SD-JWT / SD-JWT-VC is the designated future mechanism for **selective disclosure** of evidence (ADR-012 privacy upgrade path) — designed for, not faked, in V1.

## 5. SPIFFE/SPIRE

Workload identity (SVID X.509/JWT, platform-attested). Pattern to emulate for **platform-verified evidence**: our "platform_verified" quality tier plays the role of infrastructure attestation. Direct SPIFFE integration is future work when deploying inside SPIFFE-enabled estates.

## Summary

| Standard | Relevance | Adopt / Integrate | Notes |
|---|---|---|---|
| A2A AgentCard | High | Integrate (export + ingest) | JWS/Ed25519 signing; fill the optional-trust gap |
| RFC 8785 (JCS) | High | Adopt for canonicalization | Our internal canonical form: sorted-key JSON (subset semantics), JCS for interop exports |
| MCP | High | Integrate (server) + OAuth 2.1 client discipline | Trust tools exposed over MCP |
| OAuth 2.1 / PRM | High | Adopt (API auth) | Scoped bearer tokens, no ambient authority |
| DID (`did:web`) | Medium | Adopt (export format) | Key-doc portability, no chain dependency |
| W3C VC 2.0 / SD-JWT-VC | Medium | Design-for (extension point) | Selective disclosure future work |
| SPIFFE/SPIRE | Low-Med | Emulate pattern | platform-verified evidence tier |

**Sources:** [A2A specification](https://github.com/a2aproject/A2A/blob/main/docs/specification.md), [AgentCard schema reference](https://www.agentcard.net/agent-card-schema), [IETF draft-aevum-agentcard](https://www.ietf.org/archive/id/draft-aevum-agentcard-00.html), [Agent card trust optional by spec](https://proofoftech.org/blog/agent-card-trust-is-optional-by-spec/), [JWS/Ed25519/JWKS practice](https://agentlair.dev/blog/your-agent-card-is-naked/), [MCP authorization spec 2025-11-25](https://modelcontextprotocol.io/specification/2025-11-25/basic/authorization), [MCP authorization tutorial 2026-07-28](https://modelcontextprotocol.io/docs/2026-07-28/tutorials/security/authorization), [OAuth 2.1 for MCP](https://trussed.ai/resources/oauth-2-1-for-mcp-authorization-flow-security-guide), [MCP PRM practices](https://dev.to/mathewpregasen/authorization-for-mcp-oauth-21-prms-and-best-practices-9hf).
