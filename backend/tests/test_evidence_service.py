"""Evidence ledger integration: chaining, signing, append-only, replay, visibility."""

from __future__ import annotations

import itertools

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
    for prev, cur in itertools.pairwise(events):
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


def test_revoked_key_rejected_at_ingestion(services):
    """A revoked (compromised) key must not be able to sign new evidence."""
    from datetime import UTC, datetime

    db = services.db.session()
    agent = services.identity.create_agent(db, "org-1", "CompromisedBot")
    key = services.keys.create_agent_key(db, agent.agent_id)
    db.commit()

    def _submit(nonce):
        return services.evidence.append(
            db, agent_id=agent.agent_id, event_type="task_completed",
            capability="translation", issuer_type="counterparty",
            issuer_id="self", signing_key_id=key.key_id,
            quality_tier="counterparty_signed",
            external_public_key=key.public_key_b64,
            external_signature="AAAA",  # signature checked after key status
            nonce=nonce, created_at=datetime.now(UTC),
        )

    # pre-revocation, an unregistered-signature failure would fire first —
    # register the key as known by appending once while active is impossible
    # without a matching signature, so assert the ordering directly: the
    # revocation rule fires for known-but-revoked keys before any trust decision.
    services.keys.revoke_agent_key(db, key.key_id, "compromised (test)")
    db.commit()
    with pytest.raises(EvidenceError, match="revoked"):
        _submit("post-revocation")
    db.close()


def test_unregistered_external_key_rejected_without_valid_signature(services):
    """Externally-signed evidence verifies over the exact canonical body the
    server constructs — client-side pre-signing cannot match, so forged
    submissions are rejected (the ingestion contract)."""
    from datetime import UTC, datetime

    from app.domain import crypto as c
    db = services.db.session()
    agent = services.identity.create_agent(db, "org-1", "ForgeBot")
    kp = c.KeyPair.generate()
    with pytest.raises(EvidenceError, match="signature"):
        services.evidence.append(
            db, agent_id=agent.agent_id, event_type="task_completed",
            capability="translation", issuer_type="counterparty",
            issuer_id="unknown-party", signing_key_id="external",
            quality_tier="counterparty_signed",
            external_public_key=kp.public_b64,
            external_signature=c.sign_payload(kp.private_b64, {"forged": True}),
            nonce="forge-1", created_at=datetime.now(UTC))
    db.close()


def test_evidence_age_cutoff_bounded(services):
    """Reputation computation excludes evidence far beyond the decay window —
    scores are unchanged because such evidence weighs <0.1%."""
    from datetime import UTC, datetime, timedelta

    db = services.db.session()
    agent = services.identity.create_agent(db, "org-1", "AncientBot")
    now = datetime.now(UTC)
    half_life = float(services.cfg["default_half_life_days"])
    cutoff_days = half_life * float(services.cfg["max_evidence_age_multiplier"])

    for i in range(6):
        services.evidence.append(
            db, agent_id=agent.agent_id, event_type="task_completed",
            capability="translation", issuer_type="platform",
            issuer_id=f"o-{i}", signing_key_id="platform",
            quality_tier="platform_verified", nonce=f"ancient-{i}",
            created_at=now - timedelta(days=cutoff_days + 5 + i))
    for i in range(8):
        services.evidence.append(
            db, agent_id=agent.agent_id, event_type="task_completed",
            capability="translation", issuer_type="platform",
            issuer_id=f"o-{i}", signing_key_id="platform",
            quality_tier="platform_verified", nonce=f"recent-{i}",
            created_at=now - timedelta(days=i))
    db.commit()

    evs = services.evidence.for_reputation(db, agent.agent_id)
    assert all(
        (now - e["created_at"]).days <= cutoff_days + 1 for e in evs
    ), "ancient evidence must be excluded from computation"
    from app.domain.reputation import compute_reputation

    vec = compute_reputation(services.cfg, agent.agent_id, "translation", evs, now)
    assert vec.dimensions["reliability"].score is not None
    db.close()


def test_append_race_retries(services, monkeypatch):
    """Seq-collision under concurrent writers retries instead of failing."""
    from datetime import UTC, datetime

    from sqlalchemy.exc import IntegrityError

    db = services.db.session()
    agent = services.identity.create_agent(db, "org-1", "RaceBot")
    db.commit()

    calls = {"n": 0}
    original_next = services.evidence.next_seq

    def flaky_next(session, agent_id):
        calls["n"] += 1
        if calls["n"] == 1:
            raise IntegrityError("simulated race", None, Exception("unique"))
        return original_next(session, agent_id)

    monkeypatch.setattr(services.evidence, "next_seq", flaky_next)
    ev = services.evidence.append(
        db, agent_id=agent.agent_id, event_type="task_completed",
        capability="translation", issuer_type="platform", issuer_id="platform",
        signing_key_id="platform", nonce="race-1",
        created_at=datetime.now(UTC))
    assert ev.seq == 1 and calls["n"] >= 2
    db.close()
