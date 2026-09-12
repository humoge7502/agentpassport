"""Deterministic demo seed (spec §62/§63).

Creates a synthetic, clearly-labeled demo world:
  - Acme Logistics, Globex Financial (demo orgs)
  - ProcureBot, TranslationBot, FinanceBot, ResearchBot, SecurityBot, NegotiatorBot
  - realistic evidence streams (varied issuers/tiers over simulated time)
  - an endorsement graph (incl. one collusion ring for the Security Center)
  - the KILLER DEMO state: ProcureBot can discover/delegate vendor negotiation;
    NegotiatorBot's trust drops after a model replacement (epoch 2, reverify).

Run:  python -m app.demo.seed [--fresh]
"""

from __future__ import annotations

import argparse
import sys
from datetime import timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.domain import crypto                       # noqa: E402
from app.domain.reputation import compute_all_capabilities  # noqa: E402
from app.services import build_services             # noqa: E402


def _evidence_stream(svc, db, agent_id, capability, *, days_span=60, successes=28,
                     fails=2, prefix="seed"):
    """Platform-observed + counterparty + audit evidence over simulated time."""
    now = __import__("datetime").datetime.now(__import__("datetime").timezone.utc)
    import datetime as dt

    counter_kps = {c: crypto.KeyPair.generate() for c in range(2)}
    plan: list[tuple[str, str, str, int]] = []
    for i in range(successes):
        tier = ("platform_verified", "counterparty_signed", "independent_audit")[i % 3]
        issuer = ("platform", f"counterparty-{i % 2}", "external-auditor")[i % 3]
        plan.append(("task_completed", tier, issuer, i % max(1, days_span)))
    for i in range(fails):
        plan.append(("task_failed", "platform_verified", "platform", (i * 17) % max(1, days_span)))
    plan.append(("sla_met", "platform_verified", "platform", 12))
    plan.append(("audit_passed", "independent_audit", "external-auditor", 30))

    for i, (etype, tier, issuer, days_ago) in enumerate(plan):
        svc.evidence.append(
            db, agent_id=agent_id, event_type=etype, capability=capability,
            task_class=f"{capability}.standard", outcome="success" if "completed" in etype else None,
            issuer_type="platform" if issuer == "platform" else "counterparty",
            issuer_id=issuer, signing_key_id="platform", quality_tier=tier,
            visibility="org",
            context={"demo": True},
            nonce=f"{prefix}-{agent_id[:8]}-{capability}-{i}-{days_ago}",
            created_at=now - dt.timedelta(days=days_ago),
        )


def _endorse(svc, db, issuer_id, subject_id, capability, strength=0.85):
    from app.models import TrustRelationship, new_id
    db.add(TrustRelationship(
        relationship_id=new_id(), issuer_agent_id=issuer_id,
        subject_agent_id=subject_id, capability=capability,
        strength=strength, confidence=0.8, kind="endorsement",
    ))
    svc.evidence.append(
        db, agent_id=subject_id, event_type="capability_attested",
        issuer_type="counterparty", issuer_id=issuer_id, signing_key_id="platform",
        capability=capability, quality_tier="counterparty_signed",
        visibility="public", context={"demo": True},
        nonce=f"endorse-{issuer_id[:8]}-{subject_id[:8]}-{capability}",
    )


def seed(fresh: bool = True) -> dict:
    db_url = "sqlite:///./agentpassport.db" if fresh else None
    if fresh:
        for suffix in ("", "-wal", "-shm"):
            p = Path("./agentpassport.db" + suffix)
            if p.exists():
                p.unlink()
    svc = build_services(database_url=db_url)
    svc.db.create_all()
    db = svc.db.session()

    out: dict = {"agents": {}}

    # --- orgs ---------------------------------------------------------------
    svc.identity.ensure_org(db, "org-acme", "Acme Logistics (demo)")
    svc.identity.ensure_org(db, "org-globex", "Globex Financial (demo)")
    svc.identity.ensure_org(db, "org-initech", "Initech Solutions (demo)")

    # --- core agents ----------------------------------------------------------
    procure = svc.identity.create_agent(
        db, "org-acme", "ProcureBot", risk_class="high",
        model_id="atlas-4", capabilities=["procurement", "vendor_negotiation"],
        tools=["erp_connector", "email"], permissions=["po.create"])
    translation = svc.identity.create_agent(
        db, "org-acme", "TranslationBot", risk_class="low",
        model_id="lingua-2", capabilities=["translation"],
        tools=["glossary"], permissions=["docs.read"])
    finance = svc.identity.create_agent(
        db, "org-globex", "FinanceBot", risk_class="critical",
        model_id="ledger-9", capabilities=["financial_transaction", "financial_analysis"],
        tools=["payment_gateway"], permissions=["payments.execute"])
    research = svc.identity.create_agent(
        db, "org-initech", "ResearchBot", risk_class="low",
        model_id="scholar-3", capabilities=["research", "summarization"],
        tools=["web_search"], permissions=["docs.read"])
    security = svc.identity.create_agent(
        db, "org-globex", "SecurityBot", risk_class="medium",
        model_id="sentinel-5", capabilities=["security_review"],
        tools=["scanner"], permissions=["findings.write"])
    negotiator = svc.identity.create_agent(
        db, "org-initech", "NegotiatorBot", risk_class="high",
        model_id="atlas-4", capabilities=["vendor_negotiation"],
        tools=["crm_connector", "email"], permissions=["quote.request"])

    for name, agent in [("procurebot", procure), ("translationbot", translation),
                        ("financebot", finance), ("researchbot", research),
                        ("securitybot", security), ("negotiatorbot", negotiator)]:
        out["agents"][name] = agent.agent_id

    # --- evidence streams -------------------------------------------------
    _evidence_stream(svc, db, procure.agent_id, "procurement", successes=30, fails=2)
    _evidence_stream(svc, db, procure.agent_id, "vendor_negotiation", successes=18, fails=1)
    _evidence_stream(svc, db, translation.agent_id, "translation", successes=34, fails=1)
    _evidence_stream(svc, db, finance.agent_id, "financial_analysis", successes=26, fails=1)
    _evidence_stream(svc, db, finance.agent_id, "financial_transaction", successes=22, fails=2)
    _evidence_stream(svc, db, research.agent_id, "research", successes=20, fails=2)
    _evidence_stream(svc, db, security.agent_id, "security_review", successes=24, fails=1)
    # NegotiatorBot: modest history (the killer-demo subject before its model change)
    _evidence_stream(svc, db, negotiator.agent_id, "vendor_negotiation", successes=22, fails=2)

    # a policy violation on ProcureBot (shows up in Security Center, not fatal)
    svc.evidence.append(
        db, agent_id=procure.agent_id, event_type="policy_violation",
        capability="procurement", issuer_type="platform", issuer_id="platform",
        signing_key_id="platform", quality_tier="platform_verified",
        visibility="org", context={"demo": True, "rule": "max_po_value"},
        nonce="seed-procure-violation-1")

    # --- endorsements -----------------------------------------------------
    _endorse(svc, db, procure.agent_id, translation.agent_id, "translation", 0.8)
    _endorse(svc, db, finance.agent_id, procure.agent_id, "procurement", 0.7)
    _endorse(svc, db, security.agent_id, finance.agent_id, "financial_transaction", 0.75)
    _endorse(svc, db, research.agent_id, translation.agent_id, "translation", 0.6)
    # small collusion ring (3-way mutual praise between research + two helpers)
    ring_b = svc.identity.create_agent(db, "org-initech", "PraiseBot-A", capabilities=["research"])
    ring_c = svc.identity.create_agent(db, "org-initech", "PraiseBot-B", capabilities=["research"])
    out["agents"]["praisebot_a"] = ring_b.agent_id
    out["agents"]["praisebot_b"] = ring_c.agent_id
    _endorse(svc, db, research.agent_id, ring_b.agent_id, "research", 0.9)
    _endorse(svc, db, ring_b.agent_id, ring_c.agent_id, "research", 0.9)
    _endorse(svc, db, ring_c.agent_id, research.agent_id, "research", 0.9)

    # --- reputation snapshots (for trends) ----------------------------------
    for agent in (procure, translation, finance, research, security, negotiator):
        svc.reputation.snapshot(db, agent.agent_id)

    # --- killer demo delegation: ProcureBot delegates vendor negotiation ------
    deleg = svc.delegations.propose_delegation(
        db, requester_agent_id=procure.agent_id, delegate_agent_id=negotiator.agent_id,
        capability="vendor_negotiation", risk_class="high", transaction_value=75000,
        task_class="vendor_negotiation.renewal")
    out["delegation_before_model_change"] = deleg.delegation_id
    svc.delegations.complete_delegation(db, deleg.delegation_id, "completed")

    # --- THE MODEL CHANGE: NegotiatorBot swaps atlas-4 → nova-7 ---------------
    epoch2, summary = svc.identity.update_agent(
        db, negotiator, trigger="model_changed", model_id="nova-7", model_family="nova")
    svc.evidence.append(
        db, agent_id=negotiator.agent_id, event_type="model_changed",
        issuer_type="platform", issuer_id="platform", signing_key_id="platform",
        context={"demo": True, "from": "atlas-4", "to": "nova-7",
                 "continuity_factor": summary["assessment"]["factor"]},
        quality_tier="platform_verified", nonce="seed-negotiator-model-change")

    # post-change delegation decision — should now be gated (REVERIFY/DENY/HP)
    deleg2 = svc.delegations.propose_delegation(
        db, requester_agent_id=procure.agent_id, delegate_agent_id=negotiator.agent_id,
        capability="vendor_negotiation", risk_class="high", transaction_value=75000,
        task_class="vendor_negotiation.renewal")
    out["delegation_after_model_change"] = deleg2.delegation_id

    # security scan to populate incidents (collusion ring)
    from app.api_misc import run_security_scan  # reuse scan logic
    import app.services as services_module
    services_module._services = svc  # ensure scan uses this DB
    scan = run_security_scan(auth=None, db=db)
    out["scan"] = {"incidents": len(scan["incidents_created"])}

    db.commit()
    db.close()

    # console summary
    print("Seeded demo world:")
    for name, aid in out["agents"].items():
        print(f"  {name:16s} {aid}")
    print(f"  delegation before model change: {out['delegation_before_model_change']}")
    print(f"  delegation after model change:  {out['delegation_after_model_change']}"
          f"  status={deleg2.status} decision={deleg2.decision}")
    return out


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--fresh", action="store_true", default=True)
    parser.parse_args()
    seed(fresh=True)
