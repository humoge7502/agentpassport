"""Identity service: passports, keys, lifecycle, trust epochs (ADR-003/004/007)."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain import crypto
from app.domain.epochs import EpochSnapshot, assess_continuity, inherit_reputation
from app.domain.reputation import compute_all_capabilities
from app.domain.trust_config import TrustConfig
from app.models import (
    Agent,
    AgentVersion,
    AuditEvent,
    EvidenceEvent,
    Organization,
    SigningKey,
    TrustEpoch,
    new_id,
    utcnow,
)


class IdentityError(Exception):
    pass


class KeyService:
    """Server-managed Ed25519 keys (dev/demo). Custody model in SECURITY.md."""

    def __init__(self, keys_root: str):
        self.store = crypto.KeyFileStore(keys_root)

    def _platform(self) -> tuple[str, str]:
        """(key_id, private_b64) for the platform key, generating if needed."""
        kid = "platform"
        priv = self.store.get(kid)
        if priv is None:
            kp = crypto.KeyPair.generate()
            self.store.put(kid, kp.private_b64)
            priv = kp.private_b64
        return kid, priv

    def create_agent_key(self, db: Session, agent_id: str) -> SigningKey:
        key_id = f"agent-{agent_id[:12]}-{new_id()[:8]}"
        kp = crypto.KeyPair.generate()
        self.store.put(key_id, kp.private_b64)
        rec = SigningKey(
            key_id=key_id, agent_id=agent_id, scope="agent",
            public_key_b64=kp.public_b64, status="active",
        )
        db.add(rec)
        db.flush()
        return rec

    def rotate_agent_key(self, db: Session, agent: Agent) -> tuple[SigningKey, SigningKey]:
        old = db.execute(
            select(SigningKey).where(
                SigningKey.agent_id == agent.agent_id, SigningKey.status == "active"
            )
        ).scalars().first()
        new_key = self.create_agent_key(db, agent.agent_id)
        if old:
            old.status = "retired"
            old.retired_at = utcnow()
        db.add(AuditEvent(
            audit_id=new_id(), actor="platform", action="key.rotate",
            entity_type="agent", entity_id=agent.agent_id,
            before={"key_id": old.key_id if old else None},
            after={"key_id": new_key.key_id},
        ))
        return old, new_key

    def revoke_agent_key(self, db: Session, key_id: str, reason: str) -> SigningKey:
        key = db.get(SigningKey, key_id)
        if not key:
            raise IdentityError(f"key {key_id} not found")
        key.status = "revoked"
        key.revoked_at = utcnow()
        key.revocation_reason = reason
        db.add(AuditEvent(
            audit_id=new_id(), actor="platform", action="key.revoke",
            entity_type="signing_key", entity_id=key_id,
            after={"reason": reason},
        ))
        return key

    def private_for(self, key_id: str) -> str | None:
        return self.store.get(key_id)

    def platform_sign(self, payload: dict) -> tuple[str, str]:
        """Sign with platform key → (key_id, signature)."""
        kid, priv = self._platform()
        return kid, crypto.sign_payload(priv, payload)


class IdentityService:
    def __init__(self, cfg: TrustConfig, keys: KeyService):
        self.cfg = cfg
        self.keys = keys

    # -- orgs ---------------------------------------------------------------

    def ensure_org(self, db: Session, org_id: str, name: str) -> Organization:
        org = db.get(Organization, org_id)
        if org is None:
            org = Organization(org_id=org_id, name=name)
            db.add(org)
            db.flush()
        return org

    # -- lifecycle (spec §14) ----------------------------------------------

    def create_agent(
        self, db: Session, owner_org_id: str, display_name: str,
        risk_class: str = "medium", model_id: str | None = None,
        capabilities: list[str] | None = None, tools: list[str] | None = None,
        permissions: list[str] | None = None,
    ) -> Agent:
        self.ensure_org(db, owner_org_id, owner_org_id)  # FK target must exist
        agent = Agent(
            agent_id=new_id(), owner_org_id=owner_org_id,
            display_name=display_name, status="active", risk_class=risk_class,
        )
        db.add(agent)
        db.flush()
        key = self.keys.create_agent_key(db, agent.agent_id)
        epoch = TrustEpoch(
            epoch_id=new_id(), agent_id=agent.agent_id, epoch_number=1,
            trigger="created", config_snapshot={}, flags={},
        )
        db.add(epoch)
        db.flush()
        version = AgentVersion(
            version_id=new_id(), agent_id=agent.agent_id, identity_version=1,
            epoch_id=epoch.epoch_id, model_id=model_id,
            capabilities=capabilities or [], tools=tools or [],
            permissions=permissions or [], snapshot={},
        )
        db.add(version)
        epoch.config_snapshot = self._snapshot_dict(version)
        db.add(AuditEvent(
            audit_id=new_id(), actor="platform", action="agent.create",
            entity_type="agent", entity_id=agent.agent_id,
            after={"display_name": display_name, "owner": owner_org_id,
                   "key_id": key.key_id, "epoch": epoch.epoch_number},
        ))
        return agent

    def _snapshot_dict(self, v: AgentVersion) -> dict:
        return {
            "model_id": v.model_id, "model_family": v.model_family,
            "owner_org_id": None,  # filled by caller with agent.owner_org_id
            "capabilities": list(v.capabilities or []),
            "tools": list(v.tools or []),
            "permissions": list(v.permissions or []),
        }

    def current_version(self, db: Session, agent: Agent) -> AgentVersion:
        return db.execute(
            select(AgentVersion)
            .where(AgentVersion.agent_id == agent.agent_id)
            .order_by(AgentVersion.identity_version.desc())
            .limit(1)
        ).scalars().one()

    def current_epoch(self, db: Session, agent: Agent) -> TrustEpoch:
        return db.get(TrustEpoch, agent.current_epoch_id) if agent.current_epoch_id else (
            db.execute(
                select(TrustEpoch).where(TrustEpoch.agent_id == agent.agent_id)
                .order_by(TrustEpoch.epoch_number.desc()).limit(1)
            ).scalars().one()
        )

    def update_agent(
        self, db: Session, agent: Agent, trigger: str,
        model_id: str | None = None, model_family: str | None = None,
        capabilities_add: list[str] | None = None,
        capabilities_remove: list[str] | None = None,
        tools_add: list[str] | None = None, tools_remove: list[str] | None = None,
        permissions_add: list[str] | None = None,
        permissions_remove: list[str] | None = None,
        transfer_to_org: str | None = None,
        security_events_since: int = 0,
        behavior_continuity: float = 1.0,
    ) -> tuple[TrustEpoch, dict]:
        """Apply a lifecycle change → close epoch N, open N+1 with continuity
        assessment and reputation inheritance. Returns (new_epoch, summary)."""
        old_epoch = self.current_epoch(db, agent)
        old_version = self.current_version(db, agent)
        old_snapshot = EpochSnapshot(
            model_id=old_version.model_id, model_family=old_version.model_family,
            owner_org_id=agent.owner_org_id,
            capabilities=set(old_version.capabilities or []),
            tools=set(old_version.tools or []),
            permissions=set(old_version.permissions or []),
        )

        new_owner = transfer_to_org or agent.owner_org_id
        if transfer_to_org:
            self.ensure_org(db, transfer_to_org, transfer_to_org)
        new_caps = set(old_version.capabilities or [])
        new_caps |= set(capabilities_add or [])
        new_caps -= set(capabilities_remove or [])
        new_tools = set(old_version.tools or [])
        new_tools |= set(tools_add or [])
        new_tools -= set(tools_remove or [])
        new_perms = set(old_version.permissions or [])
        new_perms |= set(permissions_add or [])
        new_perms -= set(permissions_remove or [])
        new_model = model_id or old_version.model_id
        new_family = model_family or old_version.model_family
        if model_id and not model_family:
            new_family = model_id.split("-")[0] if "-" in (model_id or "") else model_id

        new_snapshot = EpochSnapshot(
            model_id=new_model, model_family=new_family, owner_org_id=new_owner,
            capabilities=new_caps, tools=new_tools, permissions=new_perms,
        )

        # historical per-capability reputation (score only) for inheritance
        hist_evidence = db.execute(
            select(EvidenceEvent).where(EvidenceEvent.agent_id == agent.agent_id)
        ).scalars().all()
        ev_dicts = [
            {
                "event_type": e.event_type, "capability": e.capability,
                "quality_tier": e.quality_tier, "issuer_id": e.issuer_id,
                "created_at": e.created_at,
            } for e in hist_evidence
        ]
        historical = compute_all_capabilities(
            self.cfg, agent.agent_id, sorted(new_caps | set(old_version.capabilities or [])),
            ev_dicts,
        )
        hist_scores = {
            cap: (vec.overall().score if vec.overall().score is not None else None)
            for cap, vec in historical.items()
            if cap != "_global"
        }

        assessment = assess_continuity(
            self.cfg, old_snapshot, new_snapshot, trigger,
            security_events_since=security_events_since,
            behavior_continuity=behavior_continuity,
        )
        inherited = inherit_reputation(self.cfg, hist_scores, assessment)

        agent.owner_org_id = new_owner
        agent.identity_version += 1
        old_epoch.ended_at = utcnow()

        new_epoch = TrustEpoch(
            epoch_id=new_id(), agent_id=agent.agent_id,
            epoch_number=old_epoch.epoch_number + 1,
            trigger=trigger, flags={"reverify": assessment.reverify},
        )
        db.add(new_epoch)
        db.flush()
        agent.current_epoch_id = new_epoch.epoch_id

        version = AgentVersion(
            version_id=new_id(), agent_id=agent.agent_id,
            identity_version=agent.identity_version, epoch_id=new_epoch.epoch_id,
            model_id=new_model, model_family=new_family,
            capabilities=sorted(new_caps), tools=sorted(new_tools),
            permissions=sorted(new_perms), snapshot={},
        )
        db.add(version)
        new_epoch.config_snapshot = {
            "model_id": new_model, "model_family": new_family,
            "owner_org_id": new_owner, "capabilities": sorted(new_caps),
            "tools": sorted(new_tools), "permissions": sorted(new_perms),
        }
        new_epoch.continuity = assessment.to_dict()
        new_epoch.reputation_baseline = {
            "inherited": {k: v for k, v in inherited.items()},
            "historical": {k: v for k, v in hist_scores.items()},
        }

        db.add(AuditEvent(
            audit_id=new_id(), actor="platform", action=f"agent.{trigger}",
            entity_type="agent", entity_id=agent.agent_id,
            before={"epoch": old_epoch.epoch_number, "model": old_version.model_id,
                    "capabilities": sorted(old_version.capabilities or []),
                    "owner": old_snapshot.owner_org_id},
            after={"epoch": new_epoch.epoch_number, "model": new_model,
                   "capabilities": sorted(new_caps), "owner": new_owner},
            why=f"continuity factor {assessment.factor:.3f}, reverify={assessment.reverify}",
        ))
        return new_epoch, {
            "assessment": assessment.to_dict(),
            "inherited": inherited,
            "new_epoch": new_epoch,
        }

    # -- passport (spec §12/§34) --------------------------------------------

    def passport_document(self, db: Session, agent: Agent) -> dict:
        """Canonical, signable passport payload (public fields only)."""
        version = self.current_version(db, agent)
        epoch = self.current_epoch(db, agent)
        active_keys = db.execute(
            select(SigningKey).where(
                SigningKey.agent_id == agent.agent_id,
                SigningKey.status.in_(["active", "retired"]),
            )
        ).scalars().all()
        return {
            "agent_id": agent.agent_id,
            "owner_org_id": agent.owner_org_id,
            "display_name": agent.display_name,
            "status": agent.status,
            "risk_class": agent.risk_class,
            "identity_version": agent.identity_version,
            "epoch_number": epoch.epoch_number,
            "epoch_flags": epoch.flags or {},
            "model_id": version.model_id,
            "model_family": version.model_family,
            "capabilities": list(version.capabilities or []),
            "tools": list(version.tools or []),
            "permissions": list(version.permissions or []),
            "keys": [
                {"key_id": k.key_id, "public_key_b64": k.public_key_b64,
                 "status": k.status, "created_at": k.created_at.isoformat()}
                for k in active_keys
            ],
            "created_at": agent.created_at.isoformat(),
            "updated_at": agent.updated_at.isoformat() if agent.updated_at else None,
        }

    def sign_passport(self, db: Session, agent: Agent) -> dict:
        doc = self.passport_document(db, agent)
        kid, sig = self.keys.platform_sign(doc)
        return {"passport": doc, "platform_key_id": kid, "signature": sig,
                "signed_at": datetime.now(UTC).isoformat()}

    def lifecycle_action(self, db: Session, agent: Agent, action: str) -> Agent:
        """suspend / revoke / reactivate — status transitions are audited."""
        if action not in {"suspend", "revoke", "reactivate"}:
            raise IdentityError(f"unknown lifecycle action {action}")
        before = agent.status
        mapping = {"suspend": "suspended", "revoke": "revoked", "reactivate": "active"}
        agent.status = mapping[action]
        db.add(AuditEvent(
            audit_id=new_id(), actor="platform", action=f"agent.{action}",
            entity_type="agent", entity_id=agent.agent_id,
            before={"status": before}, after={"status": agent.status},
        ))
        return agent
