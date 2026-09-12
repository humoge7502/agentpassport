"""Interoperability exports (ADR-011): did:web documents + VC-shaped skeleton.

The DID document is fully functional (resolvable key material, no blockchain).
The VC export is an honest extension-point skeleton: shape + signing, flagged
as not a spec-compliant VC until the SD-JWT-VC profile work lands.
"""

from __future__ import annotations

from app.domain import crypto


def did_document(agent: dict, public_base_url: str) -> dict:
    """did:web-compatible DID document for a passport (ADR-011).

    DID: did:web:{host}:agents:{agent_id} — resolution mapping lives in
    /.well-known/did-web.md; the document itself carries the Ed25519 key.
    """
    host = public_base_url.split("//", 1)[-1].rstrip("/")
    agent_id = agent["agent_id"]
    key = next((k for k in agent.get("keys", []) if k["status"] == "active"), None)
    doc: dict = {
        "@context": ["https://www.w3.org/ns/did/v1",
                     "https://w3id.org/security/suites/ed25519-2020/v1"],
        "id": f"did:web:{host}:agents:{agent_id}",
        "alsoKnownAs": [f"agentpassport:{agent_id}"],
        "verificationMethod": [],
        "authentication": [],
        "service": [{
            "id": f"did:web:{host}:agents:{agent_id}#passport",
            "type": "AgentPassport",
            "serviceEndpoint": f"{public_base_url}/api/v1/agents/{agent_id}/passport",
        }],
    }
    if key:
        vm_id = f"did:web:{host}:agents:{agent_id}#{key['key_id']}"
        doc["verificationMethod"].append({
            "id": vm_id,
            "type": "Ed25519VerificationKey2020",
            "controller": f"did:web:{host}:agents:{agent_id}",
            "publicKeyBase64": key["public_key_b64"],
        })
        doc["authentication"].append(vm_id)
    return doc


def vc_attestation_skeleton(passport_doc: dict, platform_private_b64: str | None) -> dict:
    """W3C-VC-*shaped* attestation with AgentPassport extension fields.

    HONEST LIMITATION: this demonstrates the export shape and signing path;
    it is not yet a spec-compliant VC (no @context-locked vocabulary, no
    SD-JWT selective disclosure). Track as future work (ADR-011/ADR-012).
    """
    subject = {
        "id": f"agentpassport:{passport_doc['agent_id']}",
        "type": "AgentPassport",
        "capabilities": passport_doc.get("capabilities", []),
        "risk_class": passport_doc.get("risk_class"),
        "identity_version": passport_doc.get("identity_version"),
        "trust_epoch": passport_doc.get("epoch_number"),
    }
    credential: dict = {
        "@context": ["https://www.w3.org/2018/credentials/v1"],
        "type": ["VerifiableCredential", "AgentPassportCredential"],
        "issuer": "agentpassport:platform",
        "issuanceDate": passport_doc.get("updated_at"),
        "credentialSubject": subject,
        "_note": "extension-point skeleton — not a spec-compliant VC yet",
    }
    if platform_private_b64:
        credential["proof"] = {
            "type": "Ed25519Signature2020",
            "proofPurpose": "assertionMethod",
            "verificationMethod": "agentpassport:platform",
        }
        # sign everything except the proof block itself
        proof_payload = {k: v for k, v in credential.items() if k != "proof"}
        credential["proof"]["proofValue"] = crypto.sign_payload(
            platform_private_b64, proof_payload)
    return credential


def verify_attestation(credential: dict, platform_public_b64: str) -> bool:
    """Verify a skeleton attestation produced by vc_attestation_skeleton."""
    proof = credential.get("proof")
    if not proof or "proofValue" not in proof:
        return False
    payload = {k: v for k, v in credential.items() if k != "proof"}
    return crypto.verify_payload(platform_public_b64, payload, proof["proofValue"])
