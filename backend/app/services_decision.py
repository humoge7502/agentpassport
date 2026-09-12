"""Trust decision + reputation computation services (ADR-006, spec §34/§35)."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.policy import (
    Decision,
    PolicyRule,
    Reason,
    TrustDecision,
    TrustRequest,
    evaluate,
)
from app.domain.reputation import compute_all_capabilities
from app.domain.trust_config import TrustConfig
from app.models import (
    Agent,
    PolicyRuleRecord,
    ReputationSnapshot,
    SecurityIncident,
    TrustEpoch,
    TrustRelationship,
    new_id,
)
from app.services_evidence import EvidenceService


class ReputationService:
    def __init__(self, cfg: TrustConfig, evidence: EvidenceService):
        self.cfg = cfg
        self.evidence = evidence

    def for_agent(
        self, db: Session, agent_id: str,
        capabilities: list[str] | None = None,
    ) -> dict[str, dict]:
        """Compute all capability-conditioned vectors; returns {cap: vec_dict}."""
        return {
            cap: vec.to_dict()
            for cap, vec in self.for_agent_vectors(db, agent_id, capabilities).items()
        }

    def for_agent_vectors(
        self, db: Session, agent_id: str,
        capabilities: list[str] | None = None,
    ) -> dict:
        """Raw ReputationVector objects (for pooled overall() in decisions)."""
        ev_dicts = self.evidence.for_reputation(db, agent_id)
        return compute_all_capabilities(self.cfg, agent_id, capabilities or [], ev_dicts)

    def snapshot(self, db: Session, agent_id: str) -> list[ReputationSnapshot]:
        vectors = self.for_agent(db, agent_id)
        epoch = db.execute(
            select(TrustEpoch).where(TrustEpoch.agent_id == agent_id)
            .order_by(TrustEpoch.epoch_number.desc()).limit(1)
        ).scalars().first()
        rows = []
        for cap, vector in vectors.items():
            row = ReputationSnapshot(
                snapshot_id=new_id(), agent_id=agent_id, capability=cap,
                epoch_id=epoch.epoch_id if epoch else None, vector=vector,
            )
            db.add(row)
            rows.append(row)
        db.flush()
        return rows

    def history(self, db: Session, agent_id: str, capability: str, limit: int = 60):
        return list(db.execute(
            select(ReputationSnapshot)
            .where(ReputationSnapshot.agent_id == agent_id,
                   ReputationSnapshot.capability == capability)
            .order_by(ReputationSnapshot.computed_at.desc()).limit(limit)
        ).scalars())[::-1]


class TrustDecisionService:
    """Evaluates 'should agent A do capability X, in context, at time T?'"""

    def __init__(
        self, cfg: TrustConfig, reputation: ReputationService, evidence: EvidenceService,
    ):
        self.cfg = cfg
        self.reputation = reputation
        self.evidence = evidence

    def _db_rules(self, db: Session) -> list[PolicyRule]:
        from app.domain.policy import Decision
        rows = db.execute(
            select(PolicyRuleRecord).where(PolicyRuleRecord.enabled.is_(True))
        ).scalars().all()
        out = []
        for r in rows:
            m = r.matcher or {}
            out.append(PolicyRule(
                rule_id=r.rule_id, name=r.name, outcome=Decision(r.outcome),
                priority=r.priority,
                capability=m.get("capability"), capability_prefix=m.get("capability_prefix"),
                min_transaction_value=m.get("min_transaction_value"),
                max_transaction_value=m.get("max_transaction_value"),
                min_score=m.get("min_score"), min_confidence=m.get("min_confidence"),
                max_security_score=m.get("max_security_score"),
                risk_classes=m.get("risk_classes"),
                requires_epoch_flag=m.get("requires_epoch_flag"),
            ))
        return out

    def reputation_view(self, db: Session, agent: Agent, capability: str) -> dict:
        """Reputation inputs the policy engine sees for this exact request.

        Overall aggregates use the domain's pooled confidence (total evidence
        mass + diversity), matching what the UI displays.
        """
        vectors = self.reputation.for_agent_vectors(db, agent.agent_id, [])
        # prefer exact capability, fall back to declared capability family, then _global
        vec = vectors.get(capability) or vectors.get("_global")
        overall: dict = {"score": None, "confidence": 0.0,
                         "security_score": None, "evidence_count": 0}
        if vec is not None:
            o = vec.overall()
            overall = {
                "score": o.score, "confidence": o.confidence,
                "security_score": (
                    vec.dimensions.get("security").score
                    if vec.dimensions.get("security") else None
                ),
                "evidence_count": o.evidence_count,
            }
        epoch = db.execute(
            select(TrustEpoch).where(TrustEpoch.agent_id == agent.agent_id)
            .order_by(TrustEpoch.epoch_number.desc()).limit(1)
        ).scalars().first()
        return {
            **overall,
            "epoch_flags": (epoch.flags if epoch else {}) or {},
            "epoch_number": epoch.epoch_number if epoch else None,
        }

    def evaluate_request(
        self, db: Session, request: TrustRequest, agent: Agent | None = None,
    ) -> TrustDecision:
        agent = agent or db.get(Agent, request.agent_id)
        if agent is None:
            return TrustDecision(
                decision=Decision.DENY, agent_id=request.agent_id,
                capability=request.capability,
                reasons=[Reason(
                    "unknown_agent", "no passport exists for this agent_id", "identity",
                )],
                context=request.context,
            )
        if agent.status != "active":
            return TrustDecision(
                decision=Decision.DENY, agent_id=agent.agent_id,
                capability=request.capability,
                reasons=[Reason("agent_not_active", f"agent status is {agent.status}", "policy")],
                context=request.context,
            )

        rep = self.reputation_view(db, agent, request.capability)
        decision = evaluate(self.cfg, request, rep, extra_rules=self._db_rules(db))

        # graph-level contextual check: explicit relationships can override/bolster
        rel = db.execute(
            select(TrustRelationship).where(
                TrustRelationship.subject_agent_id == agent.agent_id,
                TrustRelationship.capability.in_([request.capability, "*"]),
            )
        ).scalars().first()
        if rel and decision.decision in {Decision.ALLOW}:
            decision.context["trust_relationship"] = {
                "issuer": rel.issuer_agent_id or rel.issuer_org_id,
                "strength": rel.strength,
            }
        return decision

    def record_incident(
        self, db: Session, kind: str, severity: str,
        agent_id: str | None, detail: dict,
    ) -> SecurityIncident:
        inc = SecurityIncident(
            incident_id=new_id(), agent_id=agent_id, kind=kind,
            severity=severity, detail=detail,
        )
        db.add(inc)
        db.flush()
        return inc
