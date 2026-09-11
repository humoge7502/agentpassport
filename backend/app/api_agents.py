"""Agents API: registration, passports, lifecycle, keys, discovery, A2A card.

Route order matters: literal paths (`/discover`) are declared before the
parameterized `/{agent_id}` routes.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api_deps import AdminAuth, OptionalAuth
from app.config import get_settings
from app.db import get_db
from app.models import Agent, TrustEpoch
from app.schemas import AgentCreate, AgentUpdate, LifecycleAction
from app.services import get_services

router = APIRouter(prefix="/agents", tags=["agents"])


def _agent_or_404(db: Session, agent_id: str) -> Agent:
    agent = db.get(Agent, agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail={"error": "not_found",
                                                     "message": f"agent {agent_id} not found"})
    return agent


@router.post("", status_code=201)
def create_agent(body: AgentCreate, auth: AdminAuth = Depends(), db: Session = Depends(get_db)):
    svc = get_services()
    svc.identity.ensure_org(db, body.owner_org_id,
                            body.owner_org_name or body.owner_org_id)
    agent = svc.identity.create_agent(
        db, owner_org_id=body.owner_org_id, display_name=body.display_name,
        risk_class=body.risk_class, model_id=body.model_id,
        capabilities=body.capabilities, tools=body.tools,
        permissions=body.permissions,
    )
    passport = svc.identity.sign_passport(db, agent)
    return {"agent_id": agent.agent_id, "passport": passport}


@router.get("")
def list_agents(
    capability: str | None = None, status_filter: str | None = Query(None, alias="status"),
    org: str | None = None, limit: int = Query(50, le=200),
    auth: OptionalAuth = Depends(), db: Session = Depends(get_db),
):
    svc = get_services()
    q = select(Agent)
    if status_filter:
        q = q.where(Agent.status == status_filter)
    if org:
        q = q.where(Agent.owner_org_id == org)
    agents = db.execute(q.limit(limit)).scalars().all()
    out = []
    for agent in agents:
        version = svc.identity.current_version(db, agent)
        caps = version.capabilities or []
        if capability and capability not in caps:
            continue
        epoch = svc.identity.current_epoch(db, agent)
        out.append({
            "agent_id": agent.agent_id, "display_name": agent.display_name,
            "owner_org_id": agent.owner_org_id, "status": agent.status,
            "risk_class": agent.risk_class,
            "identity_version": agent.identity_version,
            "epoch_number": epoch.epoch_number if epoch else None,
            "capabilities": caps, "model_id": version.model_id,
        })
    return {"agents": out, "count": len(out)}


@router.get("/discover")
def discover(
    capability: str, risk_class: str = "medium", transaction_value: float | None = None,
    limit: int = Query(10, le=50), min_confidence: float | None = None,
    auth: OptionalAuth = Depends(), db: Session = Depends(get_db),
):
    """Capability-based discovery ranked by contextual trust (spec §33)."""
    svc = get_services()
    results = svc.delegations.discover(
        db, capability=capability, risk_class=risk_class,
        transaction_value=transaction_value, limit=limit,
        min_confidence=min_confidence,
    )
    return {"capability": capability, "results": results}


@router.get("/{agent_id}")
def get_agent(agent_id: str, auth: OptionalAuth = Depends(), db: Session = Depends(get_db)):
    svc = get_services()
    agent = _agent_or_404(db, agent_id)
    return {"agent": svc.identity.passport_document(db, agent)}


@router.get("/{agent_id}/passport")
def get_passport(agent_id: str, auth: OptionalAuth = Depends(), db: Session = Depends(get_db)):
    """Signed passport document (platform-signed, verifiable)."""
    svc = get_services()
    agent = _agent_or_404(db, agent_id)
    return svc.identity.sign_passport(db, agent)


@router.get("/{agent_id}/agent-card")
def get_agent_card(agent_id: str, auth: OptionalAuth = Depends(), db: Session = Depends(get_db)):
    """A2A-compatible AgentCard with AgentPassport extension (ADR-011)."""
    svc = get_services()
    settings = get_settings()
    agent = _agent_or_404(db, agent_id)
    doc = svc.identity.passport_document(db, agent)
    overall_view = svc.decisions.reputation_view(db, agent, "*")
    sec = overall_view.get("security_score")
    return {
        "name": agent.display_name,
        "description": f"AgentPassport-registered agent ({agent.risk_class} risk class)",
        "url": f"{settings.public_base_url}/api/v1/agents/{agent.agent_id}",
        "version": str(agent.identity_version),
        "capabilities": {"streaming": False, "pushNotifications": False},
        "defaultInputModes": ["application/json"],
        "defaultOutputModes": ["application/json"],
        "skills": [{"id": c, "name": c} for c in doc["capabilities"]],
        "agentpassport": {
            "passport_url": f"/api/v1/agents/{agent.agent_id}/passport",
            "agent_id": agent.agent_id,
            "trust_epoch": doc["epoch_number"],
            "status": agent.status,
            "risk_class": agent.risk_class,
            "reputation_overall": {
                "score": overall_view.get("score"),
                "confidence": overall_view.get("confidence"),
            },
            "security_score": sec,
            "keys": doc["keys"],
        },
    }


@router.post("/{agent_id}/update")
def update_agent(agent_id: str, body: AgentUpdate,
                 auth: AdminAuth = Depends(), db: Session = Depends(get_db)):
    """Configuration change → trust epoch transition with continuity + inheritance."""
    svc = get_services()
    agent = _agent_or_404(db, agent_id)
    if body.trigger == "owner_transferred" and not body.transfer_to_org:
        raise HTTPException(status_code=422, detail={
            "error": "validation_error", "message": "owner_transferred requires transfer_to_org"})
    if body.trigger == "capability_escalated" and not body.capabilities_add:
        raise HTTPException(status_code=422, detail={
            "error": "validation_error",
            "message": "capability_escalated requires capabilities_add"})
    epoch, summary = svc.identity.update_agent(
        db, agent, trigger=body.trigger, model_id=body.model_id,
        model_family=body.model_family,
        capabilities_add=body.capabilities_add, capabilities_remove=body.capabilities_remove,
        tools_add=body.tools_add, tools_remove=body.tools_remove,
        permissions_add=body.permissions_add, permissions_remove=body.permissions_remove,
        transfer_to_org=body.transfer_to_org,
    )
    svc.evidence.append(
        db, agent_id=agent.agent_id, event_type=body.trigger,
        issuer_type="platform", issuer_id="platform", signing_key_id="platform",
        context={"epoch": epoch.epoch_number,
                 "continuity_factor": summary["assessment"]["factor"]},
        quality_tier="platform_verified",
    )
    return {
        "agent_id": agent.agent_id,
        "new_epoch_number": epoch.epoch_number,
        "continuity": summary["assessment"],
        "inherited_reputation": summary["inherited"],
        "reverify_required": summary["assessment"]["reverify"],
    }


@router.post("/{agent_id}/lifecycle")
def lifecycle(agent_id: str, body: LifecycleAction,
              auth: AdminAuth = Depends(), db: Session = Depends(get_db)):
    svc = get_services()
    agent = _agent_or_404(db, agent_id)
    svc.identity.lifecycle_action(db, agent, body.action)
    return {"agent_id": agent.agent_id, "status": agent.status}


@router.get("/{agent_id}/epochs")
def list_epochs(agent_id: str, auth: OptionalAuth = Depends(), db: Session = Depends(get_db)):
    _agent_or_404(db, agent_id)
    epochs = db.execute(
        select(TrustEpoch).where(TrustEpoch.agent_id == agent_id)
        .order_by(TrustEpoch.epoch_number)
    ).scalars().all()
    return {"epochs": [
        {"epoch_id": e.epoch_id, "epoch_number": e.epoch_number, "trigger": e.trigger,
         "started_at": e.started_at.isoformat(),
         "ended_at": e.ended_at.isoformat() if e.ended_at else None,
         "config": e.config_snapshot, "continuity": e.continuity,
         "reputation_baseline": e.reputation_baseline, "flags": e.flags}
        for e in epochs
    ]}


@router.post("/{agent_id}/keys/rotate")
def rotate_key(agent_id: str, auth: AdminAuth = Depends(), db: Session = Depends(get_db)):
    svc = get_services()
    agent = _agent_or_404(db, agent_id)
    old, new = svc.keys.rotate_agent_key(db, agent)
    svc.evidence.append(db, agent_id=agent.agent_id, event_type="identity_verified",
                        issuer_type="platform", issuer_id="platform",
                        signing_key_id="platform",
                        context={"rotation": True, "old_key": old.key_id if old else None,
                                 "new_key": new.key_id},
                        quality_tier="platform_verified")
    return {"old_key_id": old.key_id if old else None, "new_key_id": new.key_id,
            "new_public_key_b64": new.public_key_b64}
