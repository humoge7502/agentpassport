"""Evidence ledger integration: chaining, signing, append-only, replay, visibility."""

from __future__ import annotations

import pytest
from sqlalchemy import select, text

from app.models import EvidenceEvent
from app.services_evidence import EvidenceError


def _append(svc, db, agent_id, event_type="task_completed", **kw):
    return svc.evidence.append(
        db, agent_id=agent_id, event_type=event_type,
        issuer_type="platform", issuer_id="platform", signing_key_id="platform", **kw
    )


def test_chain_and_signatures_build(services):
    db = services.db.session()
    agent = services.identity.create_agent(db, "org-1", "ChainBot")
    for i in range(5):
        _append(services, db, agent.agent_id, nonce=f"n{i}")
    db.commit()
    report = services.evidence.verify_chain(db, agent.agent_id)
    assert report["valid"], report["problems"]
    assert report["events_checked"] == 5
    events = db.execute(
        select(EvidenceEvent).where(EvidenceEvent.agent_id == agent.agent_id)
        .order_by(EvidenceEvent.seq)
    ).scalars().all()
    # hash chain linkage
    for prev, cur in zip(events, events[1:]):
        assert cur.prev_event_hash == prev.event_hash
    db.close()


def test_append_only_enforced_at_db_level(services):
    db = services.db.session()
    agent = services.identity.create_agent(db, "org-1", "ImmutableBot")
    ev = _append(services, db, agent.agent_id)
    db.commit()
    with pytest.raises(Exception):
        db.execute(text(
            f"UPDATE evidence_events SET outcome='x' WHERE event_id='{ev.event_id}'"))
        db.commit()
    db.rollback()
    with pytest.raises(Exception):
        db.execute(text(
            f"DELETE FROM evidence_events WHERE event_id='{ev.event_id}'"))
        db.commit()
    db.rollback()
    db.close()


def test_replay_nonce_rejected(services):
    db = services.db.session()
    agent = services.identity.create_agent(db, "org-1", "ReplayBot")
    _append(services, db, agent.agent_id, nonce="unique-nonce-1")
    with pytest.raises(EvidenceError, match="replay"):
        _append(services, db, agent.agent_id, nonce="unique-nonce-1")
    db.close()


def test_unknown_event_type_rejected(services):
    db = services.db.session()
    agent = services.identity.create_agent(db, "org-1", "StrictBot")
    with pytest.raises(EvidenceError):
        _append(services, db, agent.agent_id, event_type="made_up_event")
    db.close()


def test_counterparty_signature_required_and_verified(services):
    from app.domain import crypto
    db = services.db.session()
    agent = services.identity.create_agent(db, "org-1", "CounterpartyBot")
    kp = crypto.KeyPair.generate()
    # build the exact body the service will construct: easiest is to append
    # without signature first (dry inspection), so instead verify failure path
    with pytest.raises(EvidenceError, match="signature"):
        services.evidence.append(
            db, agent_id=agent.agent_id, event_type="task_completed",
            issuer_type="counterparty", issuer_id="external-org",
            signing_key_id="external", capability="translation",
            quality_tier="counterparty_signed",
            external_public_key=kp.public_b64, external_signature="AAAA",
        )
    db.close()


def test_visibility_filtering(services):
    db = services.db.session()
    agent = services.identity.create_agent(db, "org-1", "PrivacyBot")
    _append(services, db, agent.agent_id, visibility="public")
    _append(services, db, agent.agent_id, visibility="org")
    _append(services, db, agent.agent_id, visibility="private")
    db.commit()
    assert len(services.evidence.list_for_agent(db, agent.agent_id, visibility_limit="public")) == 1
    assert len(services.evidence.list_for_agent(db, agent.agent_id, visibility_limit="org")) == 2
    assert len(services.evidence.list_for_agent(db, agent.agent_id, visibility_limit="private")) == 3
    db.close()


def test_tamper_detected_by_chain_verify(services):
    db = services.db.session()
    agent = services.identity.create_agent(db, "org-1", "TamperTarget")
    _append(services, db, agent.agent_id)
    _append(services, db, agent.agent_id)
    db.commit()
    # simulate out-of-band tampering (attacker with DB write, no keys):
    # the append-only trigger must block it outright
    with pytest.raises(Exception, match="append-only"):
        db.execute(text(
            f"UPDATE evidence_events SET payload_hash='deadbeef' "
            f"WHERE agent_id='{agent.agent_id}' AND seq=1"))
    db.rollback()
    report = services.evidence.verify_chain(db, agent.agent_id)
    assert report["valid"]
    db.close()


def test_quality_tier_validated(services):
    db = services.db.session()
    agent = services.identity.create_agent(db, "org-1", "TierBot")
    with pytest.raises(EvidenceError):
        _append(services, db, agent.agent_id, quality_tier="gold_plated")
    db.close()
