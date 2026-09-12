"""Delegation, policy, security, and audit APIs."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api_deps import AdminAuth, OptionalAuth
from app.db import get_db
from app.models import (
    Agent,
    AuditEvent,
    Delegation,
    PolicyRuleRecord,
    ReputationSnapshot,
    SecurityIncident,
    new_id,
)
from app.schemas import DelegationComplete, DelegationPropose, PolicyRuleIn
from app.services import get_services

router = APIRouter(tags=["delegation"])


# --- delegation (spec §32) ------------------------------------------------------

@router.post("/delegations/evaluate")
def evaluate_delegation(body: DelegationPropose, auth: OptionalAuth = Depends(),
                        db: Session = Depends(get_db)):
    """Either evaluate a specific delegate or discover + rank candidates first."""
    svc = get_services()
    if db.get(Agent, body.requester_agent_id) is None:
        raise HTTPException(status_code=404, detail={
            "error": "not_found", "message": "requester agent not found"})

    if body.discover or body.delegate_agent_id is None:
        candidates = svc.delegations.discover(
            db, capability=body.capability, risk_class=body.risk_class,
            transaction_value=body.transaction_value, limit=body.discover_limit,
            exclude_agent=body.requester_agent_id,
        )
        eligible = [c for c in candidates if c["decision"] in {"ALLOW", "HUMAN_APPROVAL", "REVERIFY"}]
        if not eligible:
            return {"decision": "UNKNOWN", "candidates": candidates,
                    "message": "no eligible candidate found for this capability/risk"}
        best = eligible[0]
        deleg = svc.delegations.propose_delegation(
            db, requester_agent_id=body.requester_agent_id,
            delegate_agent_id=best["agent_id"], capability=body.capability,
            risk_class=body.risk_class, transaction_value=body.transaction_value,
            task_class=body.task_class,
        )
        return {
            "delegation": _deleg_dict(deleg), "candidates": candidates,
            "selected": best,
        }

    deleg = svc.delegations.propose_delegation(
        db, requester_agent_id=body.requester_agent_id,
        delegate_agent_id=body.delegate_agent_id, capability=body.capability,
        risk_class=body.risk_class, transaction_value=body.transaction_value,
        task_class=body.task_class,
    )
    return {"delegation": _deleg_dict(deleg)}


@router.post("/delegations/{delegation_id}/complete")
def complete_delegation(delegation_id: str, body: DelegationComplete,
                        auth: AdminAuth = Depends(), db: Session = Depends(get_db)):
    svc = get_services()
    try:
        deleg = svc.delegations.complete_delegation(
            db, delegation_id, body.outcome, body.context)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail={
            "error": "invalid_transition", "message": str(exc)}) from exc
    return _deleg_dict(deleg)


@router.post("/delegations/{delegation_id}/approve")
def approve_delegation(delegation_id: str, auth: AdminAuth = Depends(),
                       db: Session = Depends(get_db)):
    """Human approval gate (spec §18: HUMAN_APPROVAL flow)."""
    svc = get_services()
    try:
        deleg = svc.delegations.approve_after_human(db, delegation_id, "admin")
    except ValueError as exc:
        raise HTTPException(status_code=409, detail={
            "error": "invalid_transition", "message": str(exc)}) from exc
    return _deleg_dict(deleg)


@router.get("/delegations")
def list_delegations(limit: int = Query(50, le=200), auth: OptionalAuth = Depends(),
                     db: Session = Depends(get_db)):
    delegs = db.execute(
        select(Delegation).order_by(Delegation.created_at.desc()).limit(limit)
    ).scalars().all()
    return {"delegations": [_deleg_dict(d) for d in delegs]}


def _deleg_dict(d: Delegation) -> dict:
    return {
        "delegation_id": d.delegation_id, "requester_agent_id": d.requester_agent_id,
        "delegate_agent_id": d.delegate_agent_id, "capability": d.capability,
        "task_class": d.task_class, "transaction_value": d.transaction_value,
        "risk_class": d.risk_class, "decision": d.decision,
        "decision_detail": d.decision_detail, "status": d.status,
        "created_at": d.created_at.isoformat(),
        "closed_at": d.closed_at.isoformat() if d.closed_at else None,
    }


# --- policy center (spec §69) ----------------------------------------------------

policy_router = APIRouter(prefix="/policies", tags=["policy"])


@policy_router.get("")
def list_policies(auth: OptionalAuth = Depends(), db: Session = Depends(get_db)):
    rules = db.execute(select(PolicyRuleRecord)).scalars().all()
    return {"rules": [
        {"rule_id": r.rule_id, "name": r.name, "outcome": r.outcome,
         "priority": r.priority, "matcher": r.matcher, "enabled": r.enabled}
        for r in rules
    ]}


@policy_router.put("/{rule_id}")
def upsert_policy(rule_id: str, body: PolicyRuleIn, auth: AdminAuth = Depends(),
                  db: Session = Depends(get_db)):
    if body.rule_id != rule_id:
        raise HTTPException(status_code=422, detail={
            "error": "validation_error", "message": "rule_id mismatch"})
    record = db.get(PolicyRuleRecord, rule_id)
    if record is None:
        record = PolicyRuleRecord(rule_id=rule_id)
        db.add(record)
    record.name = body.name
    record.outcome = body.outcome
    record.priority = body.priority
    record.matcher = body.matcher
    record.enabled = body.enabled
    db.flush()
    db.add(AuditEvent(
        audit_id=new_id(), actor="admin", action="policy.upsert",
        entity_type="policy_rule", entity_id=rule_id, after=body.model_dump(),
    ))
    return {"rule_id": rule_id, "saved": True}


@policy_router.delete("/{rule_id}")
def delete_policy(rule_id: str, auth: AdminAuth = Depends(), db: Session = Depends(get_db)):
    record = db.get(PolicyRuleRecord, rule_id)
    if record is None:
        raise HTTPException(status_code=404, detail={"error": "not_found",
                                                     "message": "rule not found"})
    record.enabled = False
    db.add(AuditEvent(
        audit_id=new_id(), actor="admin", action="policy.disable",
        entity_type="policy_rule", entity_id=rule_id,
    ))
    return {"rule_id": rule_id, "disabled": True}


# --- security center (spec §26/§27/§42) --------------------------------------------

security_router = APIRouter(prefix="/security", tags=["security"])


@security_router.get("/incidents")
def list_incidents(kind: str | None = None, status_filter: str | None = Query(None, alias="status"),
                   limit: int = Query(100, le=500), auth: OptionalAuth = Depends(),
                   db: Session = Depends(get_db)):
    q = select(SecurityIncident).order_by(SecurityIncident.detected_at.desc()).limit(limit)
    if kind:
        q = q.where(SecurityIncident.kind == kind)
    if status_filter:
        q = q.where(SecurityIncident.status == status_filter)
    incidents = db.execute(q).scalars().all()
    return {"incidents": [
        {"incident_id": i.incident_id, "agent_id": i.agent_id, "kind": i.kind,
         "severity": i.severity, "detail": i.detail, "status": i.status,
         "detected_at": i.detected_at.isoformat()}
        for i in incidents
    ]}


@security_router.post("/scan")
def run_security_scan(auth: AdminAuth = Depends(), db: Session = Depends(get_db)):
    """On-demand Sybil/collusion/lineage scan over the trust graph."""
    from app.domain.trust_graph import cluster_security_flags, find_reciprocal_cycles
    from app.models import Agent, TrustRelationship
    svc = get_services()

    edges = db.execute(select(TrustRelationship)).scalars().all()
    agents = db.execute(select(Agent)).scalars().all()
    edge_dicts = [
        {"issuer": e.issuer_agent_id or e.issuer_org_id or "?",
         "subject": e.subject_agent_id, "capability": e.capability,
         "strength": e.strength, "confidence": e.confidence}
        for e in edges
    ]
    flags = cluster_security_flags(
        svc.cfg, edge_dicts,
        agent_owners={a.agent_id: a.owner_org_id for a in agents},
        agent_created={a.agent_id: a.created_at for a in agents},
    )
    created = []
    for pair in find_reciprocal_cycles(edge_dicts):
        # one incident per reciprocal pair (damped already in propagation)
        inc = svc.decisions.record_incident(
            db, kind="collusion", severity="medium", agent_id=None,
            detail={"type": "reciprocal_endorsement", "pair": list(pair)},
        )
        created.append(inc.incident_id)
    for cluster in flags.same_owner_clusters:
        inc = svc.decisions.record_incident(
            db, kind="sybil", severity="low", agent_id=None,
            detail={"type": "same_owner_cluster", "agents": sorted(cluster),
                    "note": "same-owner endorsements capped by policy"},
        )
        created.append(inc.incident_id)
    return {
        "scanned_edges": len(edge_dicts),
        "reciprocal_pairs": len(flags.reciprocal_pairs),
        "dense_clusters": [sorted(c) for c in flags.dense_clusters],
        "same_owner_clusters": [sorted(c) for c in flags.same_owner_clusters],
        "young_issuers": sorted(flags.young_issuers),
        "incidents_created": created,
    }


@security_router.post("/agents/{agent_id}/lineage-check")
def lineage_check(agent_id: str, auth: AdminAuth = Depends(),
                  db: Session = Depends(get_db)):
    """Reputation-laundering heuristic check (ADR-008)."""
    svc = get_services()
    from app.domain.trust_graph import lineage_risk
    from app.models import Agent, EvidenceEvent, SigningKey
    agent = db.get(Agent, agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail={"error": "not_found",
                                                     "message": "agent not found"})
    # same-owner agents with overlapping capabilities and incident history
    siblings = db.execute(
        select(Agent).where(Agent.owner_org_id == agent.owner_org_id,
                            Agent.agent_id != agent.agent_id)
    ).scalars().all()
    my_version = svc.identity.current_version(db, agent)
    my_caps = set(my_version.capabilities or [])
    overlap_max = 0.0
    for sib in siblings:
        v = svc.identity.current_version(db, sib)
        sib_caps = set(v.capabilities or [])
        if my_caps and sib_caps:
            overlap_max = max(overlap_max,
                              len(my_caps & sib_caps) / len(my_caps | sib_caps))
    incidents = db.execute(
        select(EvidenceEvent).where(
            EvidenceEvent.agent_id == agent.agent_id,
            EvidenceEvent.event_type.in_(["security_violation", "policy_violation"]),
        )
    ).scalars().all()
    db.execute(
        select(SigningKey).where(SigningKey.agent_id == agent.agent_id)
    ).scalars().all()
    result = lineage_risk(
        prior_incidents=len(incidents),
        key_overlap=False,  # key reuse across agent_ids is detected at registration
        owner_overlap=len(siblings) > 0,
        capability_overlap=overlap_max,
    )
    return {"agent_id": agent.agent_id, **result}


# --- audit (spec §40) ----------------------------------------------------------------

audit_router = APIRouter(prefix="/audit", tags=["audit"])


@audit_router.get("")
def list_audit(
    entity_type: str | None = None, entity_id: str | None = None,
    limit: int = Query(100, le=500), auth: OptionalAuth = Depends(),
    db: Session = Depends(get_db),
):
    q = select(AuditEvent).order_by(AuditEvent.created_at.desc()).limit(limit)
    if entity_type:
        q = q.where(AuditEvent.entity_type == entity_type)
    if entity_id:
        q = q.where(AuditEvent.entity_id == entity_id)
    events = db.execute(q).scalars().all()
    return {"events": [
        {"audit_id": a.audit_id, "actor": a.actor, "action": a.action,
         "entity_type": a.entity_type, "entity_id": a.entity_id,
         "before": a.before, "after": a.after, "why": a.why,
         "correlation_id": a.correlation_id, "created_at": a.created_at.isoformat()}
        for a in events
    ]}


# --- reputation snapshots feed (dashboard trends) --------------------------------------

@router.get("/reputation-trends")
def reputation_trends(
    capability: str = "translation", limit: int = Query(50, le=200),
    auth: OptionalAuth = Depends(), db: Session = Depends(get_db),
):
    snaps = db.execute(
        select(ReputationSnapshot).where(ReputationSnapshot.capability == capability)
        .order_by(ReputationSnapshot.computed_at.desc()).limit(limit)
    ).scalars().all()
    return {"capability": capability, "points": [
        {"agent_id": s.agent_id, "computed_at": s.computed_at.isoformat(),
         "vector": s.vector}
        for s in reversed(snaps)
    ]}
