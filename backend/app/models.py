"""SQLAlchemy ORM models (spec §39).

SQLite for dev (JSON via sqlalchemy JSON), PostgreSQL for compose/prod.
Evidence and audit tables are append-only — enforced by triggers (db.py).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    JSON, Boolean, DateTime, Float, ForeignKey, Index, Integer,
    String, Text, UniqueConstraint, create_engine, event,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def new_id() -> str:
    return uuid.uuid4().hex


class Base(DeclarativeBase):
    pass


from sqlalchemy import types as _satypes


class UTCDateTime(_satypes.TypeDecorator):
    """TimeZone-aware datetime that survives SQLite (which drops tzinfo).

    Canonical signing includes ISO timestamps, so what goes in must come out
    byte-identical after a round-trip through the DB.
    """

    impl = _satypes.DateTime
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is not None and value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value

    def process_result_value(self, value, dialect):
        if value is not None and value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value


class Organization(Base):
    __tablename__ = "organizations"

    org_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    did: Mapped[str | None] = mapped_column(String(300), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)

    agents: Mapped[list["Agent"]] = relationship(back_populates="organization")


class Agent(Base):
    __tablename__ = "agents"

    agent_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    owner_org_id: Mapped[str] = mapped_column(ForeignKey("organizations.org_id"))
    display_name: Mapped[str] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(20), default="active")  # draft|active|suspended|revoked
    risk_class: Mapped[str] = mapped_column(String(20), default="medium")  # low|medium|high|critical
    identity_version: Mapped[int] = mapped_column(Integer, default=1)
    current_epoch_id: Mapped[str | None] = mapped_column(ForeignKey("trust_epochs.epoch_id"), nullable=True)
    a2a_endpoint: Mapped[str | None] = mapped_column(String(500), nullable=True)
    lineage: Mapped[dict] = mapped_column(JSON, default=dict)  # prior_ids, notes for laundering analysis
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, onupdate=utcnow)

    organization: Mapped[Organization] = relationship(back_populates="agents")
    keys: Mapped[list["SigningKey"]] = relationship(back_populates="agent")
    versions: Mapped[list["AgentVersion"]] = relationship(back_populates="agent")
    epochs: Mapped[list["TrustEpoch"]] = relationship(
        back_populates="agent", foreign_keys="TrustEpoch.agent_id")


class SigningKey(Base):
    __tablename__ = "signing_keys"

    key_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    agent_id: Mapped[str | None] = mapped_column(ForeignKey("agents.agent_id"), nullable=True)
    scope: Mapped[str] = mapped_column(String(20), default="agent")  # agent|platform|issuer
    public_key_b64: Mapped[str] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(20), default="active")  # active|retired|revoked
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    retired_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    revocation_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    agent: Mapped[Agent | None] = relationship(back_populates="keys")

    __tablename__ = "signing_keys"
    __table_args__ = (
        Index("ix_signing_keys_agent_status", "agent_id", "status"),
    )


class AgentVersion(Base):
    """Immutable snapshot of the passport's behavioral config at epoch start."""

    __tablename__ = "agent_versions"

    version_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    agent_id: Mapped[str] = mapped_column(ForeignKey("agents.agent_id"))
    identity_version: Mapped[int] = mapped_column(Integer)
    epoch_id: Mapped[str | None] = mapped_column(ForeignKey("trust_epochs.epoch_id"), nullable=True)
    model_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    model_family: Mapped[str | None] = mapped_column(String(100), nullable=True)
    capabilities: Mapped[list] = mapped_column(JSON, default=list)
    tools: Mapped[list] = mapped_column(JSON, default=list)
    permissions: Mapped[list] = mapped_column(JSON, default=list)
    snapshot: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)

    agent: Mapped[Agent] = relationship(back_populates="versions")


class TrustEpoch(Base):
    __tablename__ = "trust_epochs"

    epoch_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    agent_id: Mapped[str] = mapped_column(ForeignKey("agents.agent_id"))
    epoch_number: Mapped[int] = mapped_column(Integer)
    trigger: Mapped[str] = mapped_column(String(60))  # created|model_changed|owner_transferred|...
    started_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    ended_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    config_snapshot: Mapped[dict] = mapped_column(JSON, default=dict)
    continuity: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # ContinuityAssessment
    reputation_baseline: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    flags: Mapped[dict] = mapped_column(JSON, default=dict)  # {"reverify": bool, ...}

    agent: Mapped[Agent] = relationship(
        back_populates="epochs", foreign_keys=[agent_id])

    __table_args__ = (
        UniqueConstraint("agent_id", "epoch_number", name="uq_epoch_number"),
    )


class EvidenceEvent(Base):
    """Append-only, per-agent hash-chained, signed evidence (ADR-005)."""

    __tablename__ = "evidence_events"

    event_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    agent_id: Mapped[str] = mapped_column(ForeignKey("agents.agent_id"))
    seq: Mapped[int] = mapped_column(Integer)                 # per-agent monotonic
    event_type: Mapped[str] = mapped_column(String(60))
    capability: Mapped[str | None] = mapped_column(String(120), nullable=True)
    task_class: Mapped[str | None] = mapped_column(String(120), nullable=True)
    outcome: Mapped[str | None] = mapped_column(String(30), nullable=True)
    context: Mapped[dict] = mapped_column(JSON, default=dict)
    issuer_type: Mapped[str] = mapped_column(String(30))      # self|counterparty|platform|auditor
    issuer_id: Mapped[str] = mapped_column(String(120))
    signing_key_id: Mapped[str] = mapped_column(String(64))
    signature: Mapped[str] = mapped_column(Text)
    payload_hash: Mapped[str] = mapped_column(String(80))
    prev_event_hash: Mapped[str | None] = mapped_column(String(80), nullable=True)
    event_hash: Mapped[str] = mapped_column(String(80))
    quality_tier: Mapped[str] = mapped_column(String(30), default="self_reported")
    visibility: Mapped[str] = mapped_column(String(20), default="private")  # public|org|private
    metadata_json: Mapped[dict] = mapped_column("metadata", JSON, default=dict)
    corrective_of: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)

    __table_args__ = (
        UniqueConstraint("agent_id", "seq", name="uq_agent_seq"),
        Index("ix_evidence_agent_type_time", "agent_id", "event_type", "created_at"),
        Index("ix_evidence_capability_time", "capability", "created_at"),
    )


class ReputationSnapshot(Base):
    __tablename__ = "reputation_snapshots"

    snapshot_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    agent_id: Mapped[str] = mapped_column(ForeignKey("agents.agent_id"))
    capability: Mapped[str] = mapped_column(String(120))
    epoch_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    vector: Mapped[dict] = mapped_column(JSON)          # ReputationVector.to_dict()
    computed_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)

    __table_args__ = (
        Index("ix_repsnap_agent_cap_time", "agent_id", "capability", "computed_at"),
    )


class TrustRelationship(Base):
    """Directed endorsement/delegation-grant edge: issuer trusts subject."""

    __tablename__ = "trust_relationships"

    relationship_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    issuer_agent_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    issuer_org_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    subject_agent_id: Mapped[str] = mapped_column(String(64))
    capability: Mapped[str] = mapped_column(String(120), default="*")
    strength: Mapped[float] = mapped_column(Float, default=0.5)      # 0..1
    confidence: Mapped[float] = mapped_column(Float, default=0.5)
    kind: Mapped[str] = mapped_column(String(30), default="endorsement")  # endorsement|delegation_grant
    evidence_ref: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    expires_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)

    __table_args__ = (
        Index("ix_trustrel_subject", "subject_agent_id"),
    )


class Delegation(Base):
    __tablename__ = "delegations"

    delegation_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    requester_agent_id: Mapped[str] = mapped_column(String(64))
    delegate_agent_id: Mapped[str] = mapped_column(String(64))
    capability: Mapped[str] = mapped_column(String(120))
    task_class: Mapped[str | None] = mapped_column(String(120), nullable=True)
    transaction_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    risk_class: Mapped[str] = mapped_column(String(20), default="medium")
    decision: Mapped[str] = mapped_column(String(30))   # ALLOW|DENY|HUMAN_APPROVAL|REVERIFY|UNKNOWN
    decision_detail: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(30), default="proposed")  # proposed|approved|executed|failed|rejected|pending_approval
    proposed_by: Mapped[str] = mapped_column(String(120), default="platform")
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    decided_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)


class PolicyRuleRecord(Base):
    __tablename__ = "policy_rules"

    rule_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    outcome: Mapped[str] = mapped_column(String(30))
    priority: Mapped[int] = mapped_column(Integer, default=100)
    matcher: Mapped[dict] = mapped_column(JSON, default=dict)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, onupdate=utcnow)


class SecurityIncident(Base):
    __tablename__ = "security_incidents"

    incident_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    agent_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    kind: Mapped[str] = mapped_column(String(60))   # spoofing|sybil|collusion|forged_evidence|replay|tamper|laundering|key_compromise
    severity: Mapped[str] = mapped_column(String(20), default="medium")
    detail: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(30), default="open")  # open|mitigated|dismissed
    detected_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    resolved_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)

    __table_args__ = (
        Index("ix_incidents_kind_time", "kind", "detected_at"),
    )


class AuditEvent(Base):
    """Append-only audit trail for security-sensitive state changes (spec §40)."""

    __tablename__ = "audit_events"

    audit_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    actor: Mapped[str] = mapped_column(String(120))          # role/id, never secrets
    action: Mapped[str] = mapped_column(String(80))
    entity_type: Mapped[str] = mapped_column(String(60))
    entity_id: Mapped[str] = mapped_column(String(120))
    before: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    after: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    why: Mapped[str | None] = mapped_column(Text, nullable=True)
    correlation_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)

    __table_args__ = (
        Index("ix_audit_entity_time", "entity_type", "entity_id", "created_at"),
    )


class ReplayWindow(Base):
    """Nonce/timestamp tracking for evidence submission replay defense."""

    __tablename__ = "replay_windows"

    nonce: Mapped[str] = mapped_column(String(120), primary_key=True)
    agent_id: Mapped[str] = mapped_column(String(64))
    seen_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)


def make_engine(database_url: str, echo: bool = False):
    engine = create_engine(database_url, echo=echo, future=True)
    if database_url.startswith("sqlite"):
        @event.listens_for(engine, "connect")
        def _set_sqlite_pragma(dbapi_conn, _):  # noqa: ANN001
            cur = dbapi_conn.cursor()
            cur.execute("PRAGMA foreign_keys=ON")
            cur.execute("PRAGMA journal_mode=WAL")
            cur.close()
    return engine


APPEND_ONLY_SQL = {
    # block UPDATE/DELETE on append-only tables (SQLite triggers; PG via rules in migration)
    "evidence_events": [
        """
        CREATE TRIGGER IF NOT EXISTS trg_evidence_no_update
        BEFORE UPDATE ON evidence_events
        BEGIN
            SELECT RAISE(ABORT, 'evidence_events is append-only');
        END
        """,
        """
        CREATE TRIGGER IF NOT EXISTS trg_evidence_no_delete
        BEFORE DELETE ON evidence_events
        BEGIN
            SELECT RAISE(ABORT, 'evidence_events is append-only');
        END
        """,
    ],
    "audit_events": [
        """
        CREATE TRIGGER IF NOT EXISTS trg_audit_no_update
        BEFORE UPDATE ON audit_events
        BEGIN
            SELECT RAISE(ABORT, 'audit_events is append-only');
        END
        """,
        """
        CREATE TRIGGER IF NOT EXISTS trg_audit_no_delete
        BEFORE DELETE ON audit_events
        BEGIN
            SELECT RAISE(ABORT, 'audit_events is append-only');
        END
        """,
    ],
}


def install_append_only_guards(engine) -> None:
    """Apply append-only triggers. SQLite only; PostgreSQL rules live in the
    Alembic migration (see migrations/versions)."""
    if not str(engine.url).startswith("sqlite"):
        return
    with engine.begin() as conn:
        for table, statements in APPEND_ONLY_SQL.items():
            exists = conn.exec_driver_sql(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                (table,),
            ).fetchone()
            if exists:
                for stmt in statements:
                    conn.exec_driver_sql(stmt)
