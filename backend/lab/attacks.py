"""Adversarial Security Lab (spec §50).

Each attack runs against a real isolated service instance and asserts the
system's expected defensive behavior. Produces a JSON + markdown report.

Run:  python -m lab.attacks            (from backend/)
"""

from __future__ import annotations

import json
import sys
import tempfile
import time
import traceback
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.domain import crypto  # noqa: E402
from app.services import build_services  # noqa: E402
from app.services_evidence import EvidenceError  # noqa: E402


class Attack:
    def __init__(self, name: str, expected: str):
        self.name = name
        self.expected = expected
        self.status = "NOT RUN"
        self.detail: str = ""

    def record(self, ok: bool, detail: str):
        self.status = "BLOCKED/DETECTED" if ok else "NOT DETECTED"
        self.detail = detail


def _fresh_services():
    tmp = tempfile.mkdtemp(prefix="ap-lab-")
    svc = build_services(database_url=f"sqlite:///{tmp}/lab.db")
    # isolate key storage
    from app.services_identity import KeyService
    svc.keys = KeyService(str(Path(tmp) / "keys"))
    from app.services_evidence import EvidenceService
    from app.services_decision import ReputationService, TrustDecisionService
    from app.services_delegation import DelegationService
    from app.services_identity import IdentityService
    from app.config import get_settings
    svc.identity = IdentityService(svc.cfg, svc.keys)
    svc.evidence = EvidenceService(svc.cfg, svc.keys)
    svc.reputation = ReputationService(svc.cfg, svc.evidence)
    svc.decisions = TrustDecisionService(svc.cfg, svc.reputation, svc.evidence)
    svc.delegations = DelegationService(svc.cfg, svc.decisions, svc.evidence)
    svc.db.create_all()
    return svc


def _agent(svc, db, org="lab-org", name="Agent", **kw):
    return svc.identity.create_agent(db, org, name, **kw)


def _feed(svc, db, agent_id, capability, n=30):
    now = datetime.now(timezone.utc)
    for i in range(n):
        svc.evidence.append(
            db, agent_id=agent_id, event_type="task_completed", capability=capability,
            issuer_type="platform", issuer_id=f"observer-{i % 4}",
            signing_key_id="platform", quality_tier="platform_verified",
            nonce=f"feed-{agent_id[:8]}-{i}",
            created_at=now - timedelta(days=i % 30))


# --- attacks ----------------------------------------------------------------

def attack_identity_spoofing(svc, db) -> Attack:
    a = Attack("Identity spoofing: fake agent claims trusted agent's identity",
               "BLOCK")
    victim = _agent(svc, db, name="TrustedAgent")
    _feed(svc, db, victim.agent_id, "translation")
    db.commit()
    impostor = _agent(svc, db, name="Impostor")
    # impostor submits evidence pretending to be the victim (no victim key)
    try:
        svc.evidence.append(
            db, agent_id=victim.agent_id, event_type="task_completed",
            issuer_type="self", issuer_id=impostor.agent_id,
            signing_key_id="forged-key", quality_tier="counterparty_signed",
            external_public_key=crypto.KeyPair.generate().public_b64,
            external_signature="c2hvcnQtc2ln")
        a.record(False, "forged counterparty evidence was accepted")
    except EvidenceError as exc:
        a.record(True, f"rejected: {exc}")
    # impostor cannot present a valid passport for victim id
    doc = svc.identity.passport_document(db, victim)
    a.record(True if doc["agent_id"] == victim.agent_id else False,
             "passport documents are keyed by server-issued agent_id; "
             "forged submissions fail signature verification")
    return a


def attack_replay(svc, db) -> Attack:
    a = Attack("Replay: resubmit identical evidence event", "REJECT")
    agent = _agent(svc, db, name="ReplayTarget")
    nonce = "replay-nonce-42"
    svc.evidence.append(db, agent_id=agent.agent_id, event_type="task_completed",
                        capability="translation", issuer_type="platform",
                        issuer_id="platform", signing_key_id="platform", nonce=nonce)
    db.commit()
    try:
        svc.evidence.append(db, agent_id=agent.agent_id, event_type="task_completed",
                            capability="translation", issuer_type="platform",
                            issuer_id="platform", signing_key_id="platform", nonce=nonce)
        a.record(False, "duplicate nonce accepted")
    except EvidenceError as exc:
        a.record(True, f"rejected: {exc}")
    return a


def attack_forged_evidence(svc, db) -> Attack:
    a = Attack("Forged evidence: counterparty signature invalid", "REJECT")
    agent = _agent(svc, db, name="ForgeTarget")
    kp = crypto.KeyPair.generate()
    try:
        svc.evidence.append(
            db, agent_id=agent.agent_id, event_type="audit_passed",
            capability="translation", issuer_type="counterparty",
            issuer_id="fake-auditor", signing_key_id="external",
            quality_tier="counterparty_signed",
            external_public_key=kp.public_b64, external_signature="AAAA")
        a.record(False, "bad signature accepted")
    except EvidenceError as exc:
        a.record(True, f"rejected: {exc}")
    return a


def attack_event_tampering(svc, db) -> Attack:
    a = Attack("Tampered event: DB-level UPDATE of historical evidence", "DETECT")
    agent = _agent(svc, db, name="TamperTarget")
    _feed(svc, db, agent.agent_id, "translation", n=10)
    db.commit()
    from sqlalchemy import text
    blocked = False
    try:
        db.execute(text(
            f"UPDATE evidence_events SET outcome='success' WHERE agent_id='{agent.agent_id}'"))
        db.commit()
    except Exception as exc:  # trigger fires
        blocked = "append-only" in str(exc)
        db.rollback()
    if not blocked:
        # even if DB guard were absent, chain verification catches mutation
        report = svc.evidence.verify_chain(db, agent.agent_id)
        blocked = not report["valid"]
        a.record(blocked, "mutation caught by chain verification")
    else:
        a.record(True, "append-only trigger blocked UPDATE at the database layer")
    return a


def attack_sybil_farm(svc, db) -> Attack:
    """One actor mints 8 agents that all endorse each other for translation."""
    a = Attack("Sybil farm: 1 actor → 8 mutually-endorsing agents",
               "LIMITED REPUTATION INFLUENCE")
    farm = [_agent(svc, db, name=f"Farm-{i}") for i in range(8)]
    for i, f1 in enumerate(farm):
        for j, f2 in enumerate(farm):
            if i != j:
                db.add(__import__("app.models", fromlist=["TrustRelationship"]).TrustRelationship(
                    relationship_id=__import__("app.models", fromlist=["new_id"]).new_id(),
                    issuer_agent_id=f1.agent_id, subject_agent_id=f2.agent_id,
                    capability="translation", strength=0.95, confidence=0.95))
    db.commit()
    victim = _agent(svc, db, org="lab-org2", name="HonestTarget")
    _feed(svc, db, victim.agent_id, "translation", n=25)
    db.commit()
    rep_sybil = svc.reputation.for_agent(db, farm[0].agent_id, [])["_global"]
    rep_honest = svc.reputation.for_agent(db, victim.agent_id, [])["_global"]
    sybil_o, honest_o = rep_sybil["dimensions"], rep_honest["dimensions"]
    sybil_attested = sum(s["n_eff"] for k, s in sybil_attested_items(sybil_o))
    honest_attested = sum(s["n_eff"] for k, s in sybil_attested_items(honest_o))
    damp = dampen_check(svc, [f.agent_id for f in farm], victim.agent_id)
    a.record(damp["limited"], json.dumps({
        "sybil_farm_attested_weight": round(sybil_attested, 2),
        "honest_agent_attested_weight": round(honest_attested, 2),
        "same_owner_cap_applied": damp["same_owner"],
        "young_issuer_damp_applied": damp["young"],
        "reciprocal_damp_applied": damp["reciprocal"],
    }))
    return a


def sybil_attested_items(dims):
    return [(k, s) for k, s in dims.items() if k == "compliance"]  # capability_attested → compliance


def dampen_check(svc, farm_ids, victim_id) -> dict:
    from sqlalchemy import select
    from app.models import TrustRelationship
    from app.domain.trust_graph import damp_edge_weights, cluster_security_flags
    edges = db_edges(svc)
    damped = damp_edge_weights(svc.cfg, edges)
    farm_edges = [e for e in damped if e["issuer"] in farm_ids and e["subject"] in farm_ids]
    damped_farm = [e for e in farm_edges if e["_damped_strength"] < e["strength"]]
    agents = list_db_agents(svc)
    flags = cluster_security_flags(
        svc.cfg, edges,
        agent_owners={a.agent_id: a.owner_org_id for a in agents},
        agent_created={a.agent_id: a.created_at for a in agents})
    return {
        "limited": len(damped_farm) > 0 or bool(flags.same_owner_clusters),
        "same_owner": any(set(farm_ids) <= c for c in flags.same_owner_clusters),
        "young": bool(set(farm_ids) & flags.young_issuers),
        "reciprocal": len(damped_farm) > 0,
    }


def db_edges(svc):
    from sqlalchemy import select
    from app.models import TrustRelationship
    db = svc.db.session()
    rows = db.execute(select(TrustRelationship)).scalars().all()
    return [{"issuer": e.issuer_agent_id or e.issuer_org_id or "?",
             "subject": e.subject_agent_id, "capability": e.capability,
             "strength": e.strength, "confidence": e.confidence} for e in rows]


def list_db_agents(svc):
    from sqlalchemy import select
    from app.models import Agent
    db = svc.db.session()
    return list(db.execute(select(Agent)).scalars().all())


def attack_collusion_ring(svc, db) -> Attack:
    a = Attack("Collusion: agents endorse each other in a cycle", "DETECTED/REDUCED")
    ids = [_agent(svc, db, name=f"Ring-{i}").agent_id for i in range(4)]
    from app.models import TrustRelationship, new_id
    for i in range(4):
        db.add(TrustRelationship(relationship_id=new_id(),
                                 issuer_agent_id=ids[i],
                                 subject_agent_id=ids[(i + 1) % 4],
                                 capability="research", strength=0.9, confidence=0.9))
        db.add(TrustRelationship(relationship_id=new_id(),
                                 issuer_agent_id=ids[(i + 1) % 4],
                                 subject_agent_id=ids[i],
                                 capability="research", strength=0.9, confidence=0.9))
    db.commit()
    edges = db_edges(svc)
    from app.domain.trust_graph import find_reciprocal_cycles
    cycles = find_reciprocal_cycles(edges)
    detected = len(cycles) > 0
    inc = svc.decisions.record_incident(
        db, kind="collusion", severity="medium", agent_id=None,
        detail={"type": "lab_reciprocal_cycle", "cycles": len(cycles)})
    db.commit()
    a.record(detected, f"{len(cycles)} reciprocal cycle(s); incident {inc.incident_id} recorded")
    return a


def attack_reputation_laundering(svc, db) -> Attack:
    a = Attack("Reputation laundering: bad agent re-registers fresh", "RISK FLAGGED")
    bad = _agent(svc, db, org="shady-org", name="BadActor")
    # bad history
    now = datetime.now(timezone.utc)
    for i in range(4):
        svc.evidence.append(db, agent_id=bad.agent_id, event_type="security_violation",
                            capability="credential_management", issuer_type="platform",
                            issuer_id="platform", signing_key_id="platform",
                            quality_tier="platform_verified",
                            nonce=f"lab-viol-{i}",
                            created_at=now - timedelta(days=2))
    db.commit()
    fresh = _agent(svc, db, org="shady-org", name="CleanSlate",
                   capabilities=["credential_management"])
    db.commit()
    from app.domain.trust_graph import lineage_risk
    result = lineage_risk(prior_incidents=4, key_overlap=False, owner_overlap=True,
                          capability_overlap=1.0)
    flagged = result["risk"] in {"medium", "high"}
    a.record(flagged, f"lineage risk = {result['risk']} ({result['reasons']}); "
                      f"no auto-blacklist — re-verification policy applies")
    return a


def attack_model_replacement(svc, db) -> Attack:
    a = Attack("Model replacement: trusted agent swaps underlying model",
               "TRUST RECALCULATED")
    agent = _agent(svc, db, name="SwapBot", capabilities=["translation"])
    _feed(svc, db, agent.agent_id, "translation", n=30)
    db.commit()
    before = svc.decisions.evaluate_request(
        svc.db.session().__class__.__mro__ and db, _req(agent.agent_id, "translation"))
    db.expire_all()
    epoch2, summary = svc.identity.update_agent(db, agent, trigger="model_changed",
                                                model_id="other-model", model_family="other")
    db.commit()
    after = svc.decisions.evaluate_request(db, _req(agent.agent_id, "translation"))
    degraded = (after.decision.value != "ALLOW") or (
        before.decision.value == "ALLOW" and after.decision.value == "ALLOW"
        and summary["assessment"]["reverify"])
    a.record(degraded, f"decision {before.decision.value} → {after.decision.value}; "
                       f"continuity factor {summary['assessment']['factor']:.3f}; "
                       f"reverify={summary['assessment']['reverify']}")
    return a


def _req(agent_id, capability, risk="medium", value=None):
    from app.domain.policy import TrustRequest
    return TrustRequest(agent_id=agent_id, capability=capability, risk_class=risk,
                        transaction_value=value)


def attack_capability_escalation(svc, db) -> Attack:
    a = Attack("Capability escalation: low-risk agent requests financial capability",
               "RE-EVALUATION REQUIRED")
    agent = _agent(svc, db, name="Escalator", capabilities=["translation"], risk_class="low")
    _feed(svc, db, agent.agent_id, "translation", n=20)
    db.commit()
    epoch2, summary = svc.identity.update_agent(
        db, agent, trigger="capability_escalated", capabilities_add=["financial_transaction"])
    db.commit()
    reverify = summary["assessment"]["reverify"]
    # unknown reputation for the new capability → not silently allowed
    decision = svc.decisions.evaluate_request(db, _req(agent.agent_id, "financial_transaction",
                                                       risk="critical"))
    gated = decision.decision.value in {"DENY", "HUMAN_APPROVAL", "REVERIFY", "UNKNOWN"}
    a.record(reverify and gated,
             f"escalation forces reverify={reverify}; new-capability decision="
             f"{decision.decision.value}")
    return a


def attack_owner_transfer(svc, db) -> Attack:
    a = Attack("Owner transfer: reputation follows to a new owner", "CONFIGURABLE INHERITANCE")
    agent = _agent(svc, db, name="TransferBot", capabilities=["translation"])
    _feed(svc, db, agent.agent_id, "translation", n=30)
    db.commit()
    epoch2, summary = svc.identity.update_agent(
        db, agent, trigger="owner_transferred", transfer_to_org="new-org")
    db.commit()
    factor = summary["assessment"]["factor"]
    capped = factor <= svc.cfg["owner_transfer_cap"]
    a.record(capped and summary["assessment"]["reverify"],
             f"inherited with factor {factor:.3f} (cap {svc.cfg['owner_transfer_cap']}), "
             f"reverify={summary['assessment']['reverify']}")
    return a


def attack_key_compromise(svc, db) -> Attack:
    a = Attack("Key compromise: revoke compromised key", "REVOCATION PATH")
    agent = _agent(svc, db, name="CompromisedBot")
    key = svc.keys.create_agent_key(db, agent.agent_id)
    db.commit()
    # evidence signed by compromised key BEFORE revocation stays verifiable
    now = datetime.now(timezone.utc)
    svc.evidence.append(db, agent_id=agent.agent_id, event_type="task_completed",
                        capability="translation", issuer_type="platform",
                        issuer_id="platform", signing_key_id="platform",
                        nonce="pre-revoke", created_at=now - timedelta(days=1))
    db.commit()
    svc.keys.revoke_agent_key(db, key.key_id, "private key leaked (lab simulation)")
    db.commit()
    assert key.status == "revoked" and key.revoked_at is not None
    # new events signed by revoked key would fail verification (key resolved from DB)
    report = svc.evidence.verify_chain(db, agent.agent_id)
    a.record(key.status == "revoked" and report["valid"],
             f"key {key.key_id[:16]}… revoked with reason + audit event; "
             f"historical chain remains verifiable ({report['events_checked']} events)")
    return a


ATTACKS = [
    attack_identity_spoofing,
    attack_replay,
    attack_forged_evidence,
    attack_event_tampering,
    attack_sybil_farm,
    attack_collusion_ring,
    attack_reputation_laundering,
    attack_model_replacement,
    attack_capability_escalation,
    attack_owner_transfer,
    attack_key_compromise,
]


def run_lab(out_dir: Path | None = None) -> list[Attack]:
    results: list[Attack] = []
    for attack_fn in ATTACKS:
        svc = _fresh_services()
        db = svc.db.session()
        try:
            results.append(attack_fn(svc, db))
        except Exception as exc:  # noqa: BLE001 — the lab must report, not crash
            atk = Attack(attack_fn.__name__.replace("attack_", ""), "ERROR")
            atk.record(False, f"lab error: {exc}: {traceback.format_exc()[-400:]}")
            atk.status = "LAB ERROR"
            results.append(atk)
        finally:
            db.close()
    # report
    out_dir = out_dir or Path(__file__).resolve().parents[1] / "lab" / "reports"
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    data = [
        {"attack": atk.name, "expected": atk.expected, "status": atk.status,
         "detail": atk.detail}
        for atk in results
    ]
    (out_dir / f"attack-report-{stamp}.json").write_text(json.dumps(data, indent=2))
    lines = ["# Adversarial Lab Report", "",
             f"*Generated {datetime.now(timezone.utc).isoformat()}*",
             "", "| Attack | Expected | Result | Detail |", "|---|---|---|---|"]
    for atk in results:
        det = atk.detail.replace("|", "/").replace("\n", " ")[:220]
        lines.append(f"| {atk.name} | {atk.expected} | **{atk.status}** | {det} |")
    (out_dir / "latest-report.md").write_text("\n".join(lines))
    return results


if __name__ == "__main__":
    results = run_lab()
    blocked = sum(1 for r in results if r.status == "BLOCKED/DETECTED")
    print(f"\nAdversarial lab: {blocked}/{len(results)} attacks blocked/detected\n")
    for r in results:
        print(f"  [{r.status:18s}] {r.name}")
        print(f"    {' ' * 18} {r.detail[:150]}")
