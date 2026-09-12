"""Evidence service: append-only hash-chained signed events (ADR-005).

Chain: event_hash = SHA-256(canonical(body) || prev_event_hash), per agent.
Signature: issuer's Ed25519 key over the canonical body (incl. prev hash).
Corrections are new events with `corrective_of`; history is never rewritten.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.domain import crypto
from app.domain.trust_config import TrustConfig, quality_weight
from app.models import EvidenceEvent, ReplayWindow, SigningKey, new_id

# event types accepted by the ledger (spec §19)
LIFECYCLE_EVENTS = {
    "model_changed", "tool_added", "tool_removed", "permission_changed",
    "owner_changed", "capability_added", "capability_removed",
    "identity_verified", "capability_attested",
}
BEHAVIOR_EVENTS = {
    "task_completed", "task_failed", "policy_violation", "security_violation",
    "audit_passed", "audit_failed", "sla_met", "sla_breached",
    "transaction_completed", "transaction_disputed", "human_override",
    "delegation_completed", "delegation_failed",
}
KNOWN_EVENTS = LIFECYCLE_EVENTS | BEHAVIOR_EVENTS
MAX_CLOCK_SKEW = timedelta(minutes=10)


class EvidenceError(Exception):
    pass


def evidence_body(ev: EvidenceEvent) -> dict:
    """The canonical, signed body of an evidence event (whitelist)."""
    return {
        "event_id": ev.event_id,
        "agent_id": ev.agent_id,
        "seq": ev.seq,
        "event_type": ev.event_type,
        "capability": ev.capability,
        "task_class": ev.task_class,
        "outcome": ev.outcome,
        "context": ev.context or {},
        "issuer_type": ev.issuer_type,
        "issuer_id": ev.issuer_id,
        "signing_key_id": ev.signing_key_id,
        "quality_tier": ev.quality_tier,
        "prev_event_hash": ev.prev_event_hash,
        "created_at": ev.created_at.isoformat() if ev.created_at else None,
    }


class EvidenceService:
    def __init__(self, cfg: TrustConfig, key_service):
        self.cfg = cfg
        self.keys = key_service

    def next_seq(self, db: Session, agent_id: str) -> int:
        current = db.execute(
            select(func.max(EvidenceEvent.seq)).where(EvidenceEvent.agent_id == agent_id)
        ).scalar()
        return (current or 0) + 1

    def head_hash(self, db: Session, agent_id: str) -> str | None:
        row = db.execute(
            select(EvidenceEvent.event_hash).where(EvidenceEvent.agent_id == agent_id)
            .order_by(EvidenceEvent.seq.desc()).limit(1)
        ).scalar()
        return row

    def append(
        self, db: Session, agent_id: str, event_type: str,
        issuer_type: str, issuer_id: str, signing_key_id: str,
        capability: str | None = None, task_class: str | None = None,
        outcome: str | None = None, context: dict | None = None,
        quality_tier: str | None = None, visibility: str = "private",
        metadata: dict | None = None, corrective_of: str | None = None,
        nonce: str | None = None, external_signature: str | None = None,
        external_public_key: str | None = None,
        created_at: datetime | None = None,
    ) -> EvidenceEvent:
        """Append one signed evidence event.

        - `external_public_key` + `external_signature`: counterparty-signed
          submission (platform verifies; quality tier must be counterparty_signed
          or self_reported).
        - otherwise the platform signs (platform_verified tier).
        """
        if event_type not in KNOWN_EVENTS:
            raise EvidenceError(f"unknown event_type {event_type!r}")
        if visibility not in {"public", "org", "private"}:
            raise EvidenceError(f"invalid visibility {visibility!r}")
        if quality_tier and quality_tier not in self.cfg["evidence_quality_weights"]:
            raise EvidenceError(f"unknown quality tier {quality_tier!r}")

        # replay defense: (agent, event body) nonces cannot repeat
        if nonce:
            if db.get(ReplayWindow, nonce) is not None:
                raise EvidenceError("replay detected: nonce already used")
            db.add(ReplayWindow(nonce=nonce, agent_id=agent_id))

        seq = self.next_seq(db, agent_id)
        prev = self.head_hash(db, agent_id)
        ev = EvidenceEvent(
            event_id=new_id(), agent_id=agent_id, seq=seq,
            event_type=event_type, capability=capability, task_class=task_class,
            outcome=outcome, context=context or {},
            issuer_type=issuer_type, issuer_id=issuer_id,
            signing_key_id=signing_key_id, signature="",
            quality_tier=quality_tier or "platform_verified",
            visibility=visibility, metadata_json=metadata or {},
            corrective_of=corrective_of, prev_event_hash=prev,
            created_at=created_at or datetime.now(UTC),
        )
        body = evidence_body(ev)
        ev.payload_hash = crypto.canonical_hash(body)
        ev.event_hash = crypto.sha256_hex(crypto.canonical_json(body) + (prev or "").encode())

        if external_public_key:
            if not external_signature:
                raise EvidenceError("external submission requires a signature")
            # reject far-future timestamps (clock-skew abuse)
            if ev.created_at > datetime.now(UTC) + MAX_CLOCK_SKEW:
                raise EvidenceError("event timestamp too far in the future")
            if not crypto.verify_payload(external_public_key, body, external_signature):
                raise EvidenceError("signature verification failed")
            ev.signature = external_signature
        else:
            kid, sig = self.keys.platform_sign(body)
            ev.signing_key_id = kid
            ev.signature = sig

        db.add(ev)
        db.flush()
        return ev

    def verify_chain(self, db: Session, agent_id: str) -> dict:
        """Replay the per-agent hash chain and re-verify every signature."""
        events = db.execute(
            select(EvidenceEvent).where(EvidenceEvent.agent_id == agent_id)
            .order_by(EvidenceEvent.seq)
        ).scalars().all()
        keys = {k.key_id: k.public_key_b64
                for k in db.execute(select(SigningKey)).scalars()}
        # also resolve keys held in the file store (e.g. platform key in
        # service-level contexts where no DB row exists yet)
        for key_id in {ev.signing_key_id for ev in events} - set(keys):
            priv = self.keys.private_for(key_id) if self.keys else None
            if priv:
                import base64 as _b64

                from nacl.signing import SigningKey as _SK
                keys[key_id] = _b64.b64encode(
                    bytes(_SK(_b64.b64decode(priv)).verify_key)).decode()
        prev_hash: str | None = None
        problems: list[dict] = []
        for ev in events:
            body = evidence_body(ev)
            # event_hash = SHA256(canonical(body) || prev)
            recomputed = crypto.sha256_hex(crypto.canonical_json(body) + (prev_hash or "").encode())
            if ev.prev_event_hash != prev_hash:
                problems.append({"event_id": ev.event_id, "issue": "broken_prev_pointer",
                                 "expected": prev_hash, "found": ev.prev_event_hash})
            if ev.event_hash != recomputed:
                problems.append({"event_id": ev.event_id, "issue": "hash_mismatch"})
            pub = keys.get(ev.signing_key_id)
            if pub is None or not crypto.verify_payload(pub, body, ev.signature):
                problems.append({"event_id": ev.event_id, "issue": "signature_invalid"})
            prev_hash = ev.event_hash
        return {
            "agent_id": agent_id,
            "events_checked": len(events),
            "valid": not problems,
            "problems": problems,
            "head_hash": prev_hash,
        }

    def list_for_agent(
        self, db: Session, agent_id: str, event_type: str | None = None,
        capability: str | None = None, visibility_limit: str = "public",
        limit: int = 200,
    ) -> list[EvidenceEvent]:
        """Visibility-enforced read (ADR-012): public limit hides private/org rows."""
        q = select(EvidenceEvent).where(EvidenceEvent.agent_id == agent_id)
        if event_type:
            q = q.where(EvidenceEvent.event_type == event_type)
        if capability:
            q = q.where(EvidenceEvent.capability == capability)
        if visibility_limit == "public":
            q = q.where(EvidenceEvent.visibility == "public")
        elif visibility_limit == "org":
            q = q.where(EvidenceEvent.visibility.in_(["public", "org"]))
        q = q.order_by(EvidenceEvent.seq.desc()).limit(limit)
        return list(db.execute(q).scalars())

    def for_reputation(self, db: Session, agent_id: str) -> list[dict]:
        """Evidence dicts for the reputation engine (internal, all visibilities
        — private evidence influences scores; contents are never exposed)."""
        rows = db.execute(
            select(EvidenceEvent).where(EvidenceEvent.agent_id == agent_id)
            .order_by(EvidenceEvent.seq)
        ).scalars().all()
        return [
            {
                "event_id": r.event_id, "event_type": r.event_type,
                "capability": r.capability, "task_class": r.task_class,
                "outcome": r.outcome, "quality_tier": r.quality_tier,
                "issuer_type": r.issuer_type, "issuer_id": r.issuer_id,
                "created_at": r.created_at,
            }
            for r in rows
        ]

    def evidence_weight_summary(self, events: list[dict]) -> dict:
        """Aggregate quality-tier mix for disclosure without leaking contents."""
        by_tier: dict[str, float] = {}
        for ev in events:
            tier = ev.get("quality_tier", "self_reported")
            by_tier[tier] = by_tier.get(tier, 0.0) + quality_weight(self.cfg, tier)
        total = sum(by_tier.values()) or 1e-9
        return {
            "total_weight": round(total, 3),
            "by_tier": {k: round(v / total, 3) for k, v in sorted(by_tier.items())},
        }
