"""Interoperability: DID documents, VC-shaped attestation, MCP JSON-RPC tools."""

from __future__ import annotations

import base64

import pytest
from nacl.signing import SigningKey

from app.domain.interop import did_document, vc_attestation_skeleton, verify_attestation


def _passport_doc() -> dict:
    sk = SigningKey.generate()
    pub_b64 = base64.b64encode(bytes(sk.verify_key)).decode()
    return {
        "agent_id": "agent-123",
        "owner_org_id": "org-1",
        "display_name": "Test",
        "status": "active",
        "risk_class": "medium",
        "identity_version": 2,
        "epoch_number": 3,
        "capabilities": ["translation"],
        "tools": [],
        "permissions": [],
        "keys": [{"key_id": "k1", "public_key_b64": pub_b64, "status": "active",
                  "created_at": "2026-01-01T00:00:00+00:00"}],
        "created_at": "2026-01-01T00:00:00+00:00",
        "updated_at": "2026-09-01T00:00:00+00:00",
    }


def test_did_document_shape():
    doc = did_document(_passport_doc(), "https://ap.example.com")
    assert doc["id"] == "did:web:ap.example.com:agents:agent-123"
    assert doc["verificationMethod"][0]["type"] == "Ed25519VerificationKey2020"
    assert doc["authentication"]
    assert doc["service"][0]["type"] == "AgentPassport"


def test_did_document_without_keys_has_no_verification_method():
    p = _passport_doc()
    p["keys"] = []
    doc = did_document(p, "http://localhost:8000")
    assert doc["verificationMethod"] == [] and doc["authentication"] == []


def test_vc_attestation_sign_and_verify():
    from app.domain.crypto import KeyPair, verify_payload
    kp = KeyPair.generate()
    att = vc_attestation_skeleton(_passport_doc(), kp.private_b64)
    assert att["proof"]["proofValue"]
    assert verify_attestation(att, kp.public_b64)
    # tamper → invalid
    att["credentialSubject"]["risk_class"] = "low"
    assert not verify_attestation(att, kp.public_b64)
    assert verify_payload(kp.public_b64,
                          {k: v for k, v in att.items() if k != "proof"},
                          att["proof"]["proofValue"]) is False


def test_mcp_tools_roundtrip(client, admin_headers):
    r = client.get("/api/v1/mcp/tools", headers=admin_headers)
    assert r.status_code == 200
    names = {t["name"] for t in r.json()["tools"]}
    assert {"evaluate_trust", "discover_agents", "get_passport"} <= names

    created = client.post("/api/v1/agents", headers=admin_headers, json={
        "owner_org_id": "org-mcp", "display_name": "McpBot", "capabilities": ["t"]}).json()
    agent_id = created["agent_id"]

    r = client.post("/api/v1/mcp", headers=admin_headers, json={
        "jsonrpc": "2.0", "id": 1, "method": "tools/list"})
    assert r.json()["result"]["tools"]

    r = client.post("/api/v1/mcp", headers=admin_headers, json={
        "jsonrpc": "2.0", "id": 2, "method": "tools/call",
        "params": {"name": "evaluate_trust",
                   "arguments": {"agent_id": agent_id, "capability": "t"}}})
    decision = r.json()["result"]["content"][0]["json"]
    assert decision["decision"] in {"DENY", "HUMAN_APPROVAL", "REVERIFY", "UNKNOWN"}
    assert decision["reasons"]

    r = client.post("/api/v1/mcp", headers=admin_headers, json={
        "jsonrpc": "2.0", "id": 3, "method": "tools/call",
        "params": {"name": "get_passport", "arguments": {"agent_id": agent_id}}})
    assert r.json()["result"]["content"][0]["json"]["passport"]["agent_id"] == agent_id

    r = client.post("/api/v1/mcp", headers=admin_headers, json={
        "jsonrpc": "2.0", "id": 4, "method": "tools/call",
        "params": {"name": "nope", "arguments": {}}})
    assert r.json()["error"]["code"] == -32601


def test_agent_did_and_card_endpoints(client, admin_headers):
    created = client.post("/api/v1/agents", headers=admin_headers, json={
        "owner_org_id": "org-i", "display_name": "InteropBot",
        "capabilities": ["t"]}).json()
    aid = created["agent_id"]
    r = client.get(f"/api/v1/agents/{aid}/did.json")
    assert r.status_code == 200 and r.json()["id"].endswith(f"agents:{aid}")
    r = client.get(f"/api/v1/agents/{aid}/attestation")
    assert r.status_code == 200 and r.json()["proof"]["proofValue"]
    r = client.get(f"/api/v1/agents/{aid}/agent-card")
    assert r.status_code == 200 and "agentpassport" in r.json()


@pytest.mark.parametrize("visibility,admin,expected", [
    ("public", False, 1), ("org", False, 1), ("private", False, 1),  # anon clamped → public
    ("private", True, 3), ("org", True, 2),
])
def test_evidence_visibility_matrix(client, admin_headers, visibility, admin, expected):
    """Anonymous readers see public rows only (ADR-012); admin sees all."""
    created = client.post("/api/v1/agents", headers=admin_headers, json={
        "owner_org_id": "org-v", "display_name": "VisBot", "capabilities": ["t"]}).json()
    aid = created["agent_id"]
    for i, vis in enumerate(["public", "org", "private"]):
        client.post("/api/v1/evidence", headers=admin_headers, json={
            "agent_id": aid, "event_type": "task_completed", "capability": "t",
            "visibility": vis, "nonce": f"vis-{vis}-{i}"})
    headers = admin_headers if admin else {}
    r = client.get(f"/api/v1/agents/{aid}/evidence?visibility={visibility}", headers=headers)
    assert len(r.json()["events"]) == expected
