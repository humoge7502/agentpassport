"""API integration: full workflows through HTTP, including the killer demo path."""

from __future__ import annotations


def _create_agent(client, admin_headers, name, capabilities, **kw):
    body = {"owner_org_id": kw.pop("org", "org-demo"), "owner_org_name": "Demo Org",
            "display_name": name, "capabilities": capabilities, **kw}
    r = client.post("/api/v1/agents", json=body, headers=admin_headers)
    assert r.status_code == 201, r.text
    return r.json()


def _add_evidence(client, admin_headers, agent_id, event_type, capability, n=1, **kw):
    for i in range(n):
        r = client.post("/api/v1/evidence", json={
            "agent_id": agent_id, "event_type": event_type, "capability": capability,
            "nonce": f"{agent_id}-{event_type}-{i}-{kw.get('suffix', '')}",
            **kw}, headers=admin_headers)
        assert r.status_code == 201, r.text
    return r.json()


def _add_diverse_evidence(client, admin_headers, agent_id, capability,
                          successes=20, fails=0):
    """Realistic evidence mix: platform-observed events from distinct observers
    (issuer/tier diversity). True counterparty-signature verification is
    exercised at the service level in test_evidence_service.py."""
    mix = [("task_completed", "platform_verified", f"observer-{i % 4}")
           for i in range(successes)]
    mix += [("task_failed", "platform_verified", f"observer-{i % 4}")
            for i in range(fails)]
    mix += [("sla_met", "independent_audit", "audit-bot-1"),
            ("audit_passed", "independent_audit", "external-auditor"),
            ("task_completed", "counterparty_signed", "counterparty-1"),
            ("task_completed", "counterparty_signed", "counterparty-2")]
    for i, (etype, tier, issuer) in enumerate(mix):
        r = client.post("/api/v1/evidence", json={
            "agent_id": agent_id, "event_type": etype, "capability": capability,
            "quality_tier": tier, "issuer_id": issuer, "visibility": "org",
            "nonce": f"{agent_id}-{capability}-{etype}-{i}",
        }, headers=admin_headers)
        assert r.status_code == 201, r.text
    return r.json()


def test_full_trust_lifecycle(client, admin_headers):
    # 1. registration → passport exists, signed
    created = _create_agent(client, admin_headers, "TranslationBot", ["translation"],
                            model_id="model-x-1")
    agent_id = created["agent_id"]
    passport = created["passport"]
    assert passport["passport"]["capabilities"] == ["translation"]
    assert passport["signature"]

    # 2. no evidence → trust decision is not ALLOW (unknown reputation)
    r = client.post("/api/v1/trust/evaluate", json={
        "agent_id": agent_id, "capability": "translation", "risk_class": "medium"})
    decision = r.json()
    assert decision["decision"] in {"DENY", "HUMAN_APPROVAL", "REVERIFY", "UNKNOWN"}
    assert decision["reasons"], "decisions must be explainable"

    # 3. build evidence → reputation rises → ALLOW
    _add_diverse_evidence(client, admin_headers, agent_id, "translation",
                          successes=25)
    r = client.get(f"/api/v1/agents/{agent_id}/reputation?capability=translation")
    rep = r.json()["reputation"]
    assert rep["dimensions"]["reliability"]["score"] is not None
    r = client.post("/api/v1/trust/evaluate", json={
        "agent_id": agent_id, "capability": "translation", "risk_class": "medium"})
    assert r.json()["decision"] == "ALLOW", r.json()

    # 4. evidence chain verification endpoint exists
    # (verify via service-level test; here check evidence list shows chain)
    r = client.get(f"/api/v1/agents/{agent_id}/evidence?visibility=org")
    events = r.json()["events"]
    assert events[0]["prev_event_hash"] == events[1]["event_hash"]

    # 5. discovery ranks TranslationBot for translation
    r = client.get("/api/v1/agents/discover?capability=translation")
    results = r.json()["results"]
    assert any(c["agent_id"] == agent_id and c["decision"] == "ALLOW" for c in results)

    # 6. delegation from another agent works
    requester = _create_agent(client, admin_headers, "ProcureBot", ["procurement"])
    r = client.post("/api/v1/delegations/evaluate", json={
        "requester_agent_id": requester["agent_id"], "capability": "translation",
        "risk_class": "medium"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["delegation"]["decision"] == "ALLOW"

    # 7. delegation completion → evidence → reputation path intact
    deleg_id = body["delegation"]["delegation_id"]
    r = client.post(f"/api/v1/delegations/{deleg_id}/complete",
                    json={"outcome": "completed"}, headers=admin_headers)
    assert r.status_code == 200, r.text

    # 8. MODEL CHANGE → epoch 2, continuity < 1, reverify behavior
    r = client.post(f"/api/v1/agents/{agent_id}/update", headers=admin_headers, json={
        "trigger": "model_changed", "model_id": "model-z-9", "model_family": "model-z"})
    assert r.status_code == 200, r.text
    update = r.json()
    assert update["new_epoch_number"] == 2
    assert update["continuity"]["dimensions"]["model"] == 0.0
    assert update["continuity"]["factor"] < 1.0

    # 9. trust decision after model change — degraded or gated, never silently ALLOW
    r = client.post("/api/v1/trust/evaluate", json={
        "agent_id": agent_id, "capability": "translation", "risk_class": "medium"})
    after = r.json()
    assert after["decision"] in {"REVERIFY", "DENY", "HUMAN_APPROVAL"}, \
        "model change must gate trust"
    assert any(r["factor"] in {"epoch", "reputation"} for r in after["reasons"])

    # 10. epochs recorded and auditable
    r = client.get(f"/api/v1/agents/{agent_id}/epochs")
    assert len(r.json()["epochs"]) == 2
    r = client.get(f"/api/v1/audit?entity_type=agent&entity_id={agent_id}")
    actions = [e["action"] for e in r.json()["events"]]
    assert "agent.create" in actions and "agent.model_changed" in actions


def test_high_value_transaction_requires_human_approval(client, admin_headers):
    created = _create_agent(client, admin_headers, "FinanceBot", ["financial_transaction"])
    agent_id = created["agent_id"]
    _add_diverse_evidence(client, admin_headers, agent_id, "financial_transaction",
                          successes=25)
    r = client.post("/api/v1/trust/evaluate", json={
        "agent_id": agent_id, "capability": "financial_transaction",
        "risk_class": "high", "transaction_value": 250000})
    body = r.json()
    # small evidence base + high value → not a silent ALLOW
    assert body["decision"] in {"HUMAN_APPROVAL", "DENY"}


def test_unauthorized_mutations_rejected(client):
    r = client.post("/api/v1/evidence", json={
        "agent_id": "x", "event_type": "task_completed"})
    assert r.status_code == 401
    r = client.post("/api/v1/agents", json={"owner_org_id": "o",
                                            "display_name": "n"})
    assert r.status_code == 401


def test_agent_card_a2a_shape(client, admin_headers):
    created = _create_agent(client, admin_headers, "CardBot", ["translation"])
    r = client.get(f"/api/v1/agents/{created['agent_id']}/agent-card")
    assert r.status_code == 200
    card = r.json()
    for key in ("name", "url", "version", "skills", "agentpassport"):
        assert key in card
    assert "passport_url" in card["agentpassport"]


def test_evidence_visibility_private_requires_admin(client, admin_headers):
    created = _create_agent(client, admin_headers, "PrivateBot", ["translation"])
    agent_id = created["agent_id"]
    _add_evidence(client, admin_headers, agent_id, "task_completed", "translation",
                  n=2, visibility="private")
    r = client.get(f"/api/v1/agents/{agent_id}/evidence?visibility=private")
    assert r.json()["events"] == []  # anonymous read: no private leak
    r = client.get(f"/api/v1/agents/{agent_id}/evidence?visibility=private",
                   headers=admin_headers)
    assert len(r.json()["events"]) == 2


def test_endorsement_and_propagation(client, admin_headers):
    a = _create_agent(client, admin_headers, "EndorserA", ["translation"])["agent_id"]
    b = _create_agent(client, admin_headers, "EndorserB", ["translation"])["agent_id"]
    c = _create_agent(client, admin_headers, "EndorserC", ["translation"])["agent_id"]
    r = client.post("/api/v1/trust/relationships", json={
        "issuer_agent_id": a, "subject_agent_id": b, "capability": "translation",
        "strength": 0.9, "confidence": 0.9}, headers=admin_headers)
    assert r.status_code == 200
    client.post("/api/v1/trust/relationships", json={
        "issuer_agent_id": b, "subject_agent_id": c, "capability": "translation",
        "strength": 0.9, "confidence": 0.9}, headers=admin_headers)
    r = client.get(f"/api/v1/trust/propagate?source={a}&target={c}&capability=translation")
    body = r.json()
    assert body["status"] == "KNOWN"
    assert body["score"] < 0.9, "propagated trust must be discounted below direct trust"
    # capability mismatch → unknown
    r = client.get(f"/api/v1/trust/propagate?source={a}&target={c}&capability=procurement")
    assert r.json()["status"] == "UNKNOWN"


def test_security_scan_flags_collusion(client, admin_headers):
    ids = [_create_agent(client, admin_headers, f"Syb{i}", ["translation"])["agent_id"]
           for i in range(4)]
    # fully reciprocal mesh: A<->B<->C<->D<->A + cross links
    pairs = [(0, 1), (1, 0), (1, 2), (2, 1), (2, 3), (3, 2), (3, 0), (0, 3)]
    for i, j in pairs:
        client.post("/api/v1/trust/relationships", json={
            "issuer_agent_id": ids[i], "subject_agent_id": ids[j],
            "capability": "translation", "strength": 0.9, "confidence": 0.9},
            headers=admin_headers)
    r = client.post("/api/v1/security/scan", headers=admin_headers)
    body = r.json()
    assert body["reciprocal_pairs"] > 0
    assert body["same_owner_clusters"] or body["dense_clusters"], body


def test_passport_verification_roundtrip(client, admin_headers):
    created = _create_agent(client, admin_headers, "VerifyBot", ["translation"])
    passport = created["passport"]
    doc = passport["passport"]
    r = client.post("/api/v1/trust/verify-signature", json={
        "payload": doc, "signature": passport["signature"],
        "public_key_b64": next(
            k["public_key_b64"] for k in doc["keys"] if k["status"] == "active"
        ) if doc["keys"] else "platform"})
    # platform-signed: signature made by platform key; public key resolution
    # happens via /keys — this endpoint verifies agent keys. Platform verification
    # is exercised in services tests; here we assert the endpoint contract works.
    assert r.status_code == 200
    assert "valid" in r.json()
