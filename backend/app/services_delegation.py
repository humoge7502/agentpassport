"""Delegation + discovery engines (spec §32/§33).

Discovery ranks candidates by contextual trust for a capability; delegation
evaluates a specific delegation request through the policy engine and records
the full decision for audit.
"""

from __future__ import annotations

from dataclasses import asdict
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.policy import Decision, TrustRequest
from app.domain.trust_config import TrustConfig
from app.models import Agent, AgentVersion, Delegation, new_id
from app.services_decision import TrustDecisionService


class DelegationService:
    def __init__(self, cfg: TrustConfig, decisions: TrustDecisionService, evidence_service=None):
        self.cfg = cfg
        self.decisions = decisions
        self.evidence = evidence_service

    def discover(
        self, db: Session, capability: str, risk_class: str = "medium",
        transaction_value: float | None = None, limit: int = 10,
        min_confidence: float | None = None, exclude_agent: str | None = None,
    ) -> list[dict]:
        """Capability-based discovery ranked by contextual trust (not popularity)."""
        min_conf = min_confidence if min_confidence is not None else float(
            self.cfg["default_confidence_floor"].get(risk_class, 0.5)
        )
        # candidates: active agents declaring the capability
        rows = db.execute(
            select(Agent, AgentVersion)
            .join(AgentVersion, AgentVersion.agent_id == Agent.agent_id)
            .where(Agent.status == "active", AgentVersion.capabilities.contains([capability]))
            .order_by(AgentVersion.identity_version.desc())
        ).all()
        seen: set[str] = set()
        results: list[dict] = []
        for agent, _version in rows:
            if agent.agent_id in seen or agent.agent_id == exclude_agent:
                continue
            seen.add(agent.agent_id)
            rep = self.decisions.reputation_view(db, agent, capability)
            decision = self.decisions.evaluate_request(db, TrustRequest(
                agent_id=agent.agent_id, capability=capability,
                risk_class=risk_class, transaction_value=transaction_value,
                context={"source": "discovery"},
            ), agent=agent)
            results.append({
                "agent_id": agent.agent_id,
                "display_name": agent.display_name,
                "owner_org_id": agent.owner_org_id,
                "risk_class": agent.risk_class,
                "score": rep.get("score"),
                "confidence": rep.get("confidence"),
                "security_score": rep.get("security_score"),
                "evidence_count": rep.get("evidence_count"),
                "decision": decision.decision.value,
                "reasons": [asdict(r) for r in decision.reasons],
                "meets_confidence_floor": (rep.get("confidence") or 0.0) >= min_conf,
            })
        # rank: decision outcome first, then score, then confidence — UNKNOWN
        # reputation sorts below any known score, not by name-luck.
        def rank(r: dict) -> tuple:
            outcome_rank = {"ALLOW": 0, "REVERIFY": 1, "HUMAN_APPROVAL": 2,
                            "UNKNOWN": 3, "DENY": 4}.get(r["decision"], 3)
            score = r["score"] if r["score"] is not None else -1.0
            return (outcome_rank, -score, -(r["confidence"] or 0.0))
        results.sort(key=rank)
        return results[:limit]

    def propose_delegation(
        self, db: Session, requester_agent_id: str, delegate_agent_id: str,
        capability: str, risk_class: str = "medium",
        transaction_value: float | None = None, task_class: str | None = None,
        proposed_by: str = "platform",
    ) -> Delegation:
        """Full delegation evaluation: discover→select happened; this gates it."""
        decision = self.decisions.evaluate_request(db, TrustRequest(
            agent_id=delegate_agent_id, capability=capability,
            risk_class=risk_class, transaction_value=transaction_value,
            context={"delegation_from": requester_agent_id},
        ))
        status_map = {
            Decision.ALLOW: "approved", Decision.DENY: "rejected",
            Decision.HUMAN_APPROVAL: "pending_approval",
            Decision.REVERIFY: "pending_approval",
            Decision.UNKNOWN: "pending_approval",
        }
        deleg = Delegation(
            delegation_id=new_id(), requester_agent_id=requester_agent_id,
            delegate_agent_id=delegate_agent_id, capability=capability,
            task_class=task_class, transaction_value=transaction_value,
            risk_class=risk_class, decision=decision.decision.value,
            decision_detail=decision.to_dict(),
            status=status_map[decision.decision], proposed_by=proposed_by,
            decided_at=datetime.now(UTC),
        )
        db.add(deleg)
        db.flush()
        return deleg

    def complete_delegation(
        self, db: Session, delegation_id: str, outcome: str, context: dict | None = None,
    ) -> Delegation:
        """Record delegation outcome → evidence event → reputation update path."""
        deleg = db.get(Delegation, delegation_id)
        if deleg is None:
            raise ValueError(f"delegation {delegation_id} not found")
        if deleg.status not in {"approved", "pending_approval", "executed"}:
            raise ValueError(f"cannot complete delegation in status {deleg.status}")
        if outcome not in {"completed", "failed"}:
            raise ValueError("outcome must be completed|failed")

        deleg.status = "executed" if outcome == "completed" else "failed"
        deleg.closed_at = datetime.now(UTC)

        if self.evidence is not None:
            self.evidence.append(
                db,
                agent_id=deleg.delegate_agent_id,
                event_type="delegation_completed" if outcome == "completed"
                else "delegation_failed",
                issuer_type="platform", issuer_id="platform",
                signing_key_id="platform",
                capability=deleg.capability, task_class=deleg.task_class,
                outcome=outcome,
                context={"delegation_id": deleg.delegation_id,
                         "requester": deleg.requester_agent_id, **(context or {})},
                quality_tier="platform_verified",
            )
        return deleg

    def approve_after_human(self, db: Session, delegation_id: str, approver: str) -> Delegation:
        deleg = db.get(Delegation, delegation_id)
        if deleg is None or deleg.status != "pending_approval":
            raise ValueError("delegation not pending approval")
        deleg.status = "approved"
        deleg.decision_detail["human_approval"] = {
            "approver": approver, "approved_at": datetime.now(UTC).isoformat(),
        }
        db.add(AuditCompat(deleg))
        return deleg


def AuditCompat(deleg: Delegation):
    """Small helper to build an audit event for human approvals."""
    from app.models import AuditEvent
    return AuditEvent(
        audit_id=new_id(), actor="human_operator", action="delegation.approve",
        entity_type="delegation", entity_id=deleg.delegation_id,
        before={"status": "pending_approval"}, after={"status": "approved"},
    )


class DiscoveryService(DelegationService):
    """Alias namespace for API wiring; behavior identical to DelegationService.discover."""

    def search(self, *args, **kwargs):
        return self.discover(*args, **kwargs)
