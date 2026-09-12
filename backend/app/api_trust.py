"""Trust API: reputation, evidence, trust evaluation, relationships, graph."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api_deps import AdminAuth, OptionalAuth
from app.config import get_settings
from app.db import get_db
from app.domain.crypto import verify_payload
from app.domain.policy import TrustRequest
from app.models import Agent, TrustRelationship, new_id
from app.schemas import EndorsementIn, EvidenceSubmit, SignatureVerifyIn, TrustEvaluate
from app.services import get_services
from app.services_evidence import EvidenceError

router = APIRouter(tags=["trust"])


# --- reputation ---------------------------------------------------------------

@router.get("/agents/{agent_id}/reputation")
def get_reputation(
    agent_id: str, capability: str | None = None,
    history: bool = False, limit: int = Query(30, le=120),
    auth: OptionalAuth = Depends(), db: Session = Depends(get_db),
):
    svc = get_services()
    if db.get(Agent, agent_id) is None:
        raise HTTPException(status_code=404, detail={"error": "not_found",
                                                     "message": "agent not found"})
    vectors = svc.reputation.for_agent(db, agent_id, [])
    if capability:
        vector = vectors.get(capability) or vectors.get("_global")
        if vector is None:
            raise HTTPException(status_code=404, detail={
                "error": "not_found", "message": f"no reputation for capability {capability}"})
        out: dict = {"reputation": vector}
        if history:
            snaps = svc.reputation.history(db, agent_id, capability, limit)
            out["history"] = [
                {"computed_at": s.computed_at.isoformat(), "vector": s.vector}
                for s in snaps
            ]
        return out
    return {"reputations": vectors}


@router.post("/agents/{agent_id}/reputation/snapshot")
def snapshot_reputation(agent_id: str, auth: AdminAuth = Depends(),
                        db: Session = Depends(get_db)):
    svc = get_services()
    if db.get(Agent, agent_id) is None:
        raise HTTPException(status_code=404, detail={"error": "not_found",
                                                     "message": "agent not found"})
    rows = svc.reputation.snapshot(db, agent_id)
    return {"snapshots": len(rows), "capabilities": [r.capability for r in rows]}


# --- trust decisions -----------------------------------------------------------

@router.post("/trust/evaluate")
def evaluate_trust(body: TrustEvaluate, auth: OptionalAuth = Depends(),
                   db: Session = Depends(get_db)):
    """The central question: should agent A do capability X, now, at risk R?"""
    svc = get_services()
    decision = svc.decisions.evaluate_request(db, TrustRequest(
        agent_id=body.agent_id, capability=body.capability,
        risk_class=body.risk_class, transaction_value=body.transaction_value,
        context=body.context,
    ))
    return decision.to_dict()


@router.post("/trust/verify-signature")
def verify_signature(body: SignatureVerifyIn, auth: OptionalAuth = Depends()):
    """Utility: verify an Ed25519 signature over canonical JSON (open verifiability)."""
    ok = verify_payload(body.public_key_b64, body.payload, body.signature)
    return {"valid": ok}


# --- trust graph ---------------------------------------------------------------

@router.get("/trust/graph")
def trust_graph(
    agent_id: str | None = None, depth_limit: int = Query(2, le=4),
    auth: OptionalAuth = Depends(), db: Session = Depends(get_db),
):
    get_services()
    edges_q = select(TrustRelationship)
    if agent_id:
        edges_q = edges_q.where(
            (TrustRelationship.subject_agent_id == agent_id)
            | (TrustRelationship.issuer_agent_id == agent_id)
        )
    edges = db.execute(edges_q.limit(500)).scalars().all()
    nodes: dict[str, dict] = {}
    for e in edges:
        for a in (e.issuer_agent_id, e.subject_agent_id):
            if a and a not in nodes:
                agent = db.get(Agent, a)
                if agent:
                    nodes[a] = {"id": a, "label": agent.display_name,
                                "org": agent.owner_org_id, "status": agent.status}
    return {
        "nodes": list(nodes.values()),
        "edges": [
            {"id": e.relationship_id, "source": e.issuer_agent_id or e.issuer_org_id,
             "target": e.subject_agent_id, "capability": e.capability,
             "strength": e.strength, "confidence": e.confidence, "kind": e.kind}
            for e in edges
        ],
    }


@router.post("/trust/relationships")
def add_relationship(body: EndorsementIn, auth: AdminAuth = Depends(),
                     db: Session = Depends(get_db)):
    """Record an endorsement/delegation-grant edge (issuer-signed in production)."""
    svc = get_services()
    if db.get(Agent, body.subject_agent_id) is None:
        raise HTTPException(status_code=404, detail={
            "error": "not_found", "message": "subject agent not found"})
    if body.issuer_agent_id and db.get(Agent, body.issuer_agent_id) is None:
        raise HTTPException(status_code=404, detail={
            "error": "not_found", "message": "issuer agent not found"})
    rel = TrustRelationship(
        relationship_id=new_id(),
        issuer_agent_id=body.issuer_agent_id,
        subject_agent_id=body.subject_agent_id,
        capability=body.capability, strength=body.strength,
        confidence=body.confidence,
    )
    db.add(rel)
    db.flush()
    # endorsements are evidence too
    svc.evidence.append(
        db, agent_id=body.subject_agent_id, event_type="capability_attested",
        issuer_type="counterparty", issuer_id=body.issuer_agent_id or "external",
        signing_key_id="platform", capability=body.capability,
        context={"relationship_id": rel.relationship_id, "strength": body.strength},
        quality_tier="counterparty_signed",
    )
    return {"relationship_id": rel.relationship_id}


@router.get("/trust/propagate")
def propagate(
    source: str, target: str, capability: str,
    auth: OptionalAuth = Depends(), db: Session = Depends(get_db),
):
    """Contextual, non-transitive trust propagation (ADR-008)."""
    svc = get_services()
    edges = db.execute(select(TrustRelationship).limit(2000)).scalars().all()
    edge_dicts = [
        {"issuer": e.issuer_agent_id or e.issuer_org_id or "?",
         "subject": e.subject_agent_id, "capability": e.capability,
         "strength": e.strength, "confidence": e.confidence}
        for e in edges
    ]
    from app.domain.trust_graph import propagate_trust
    return propagate_trust(svc.cfg, edge_dicts, source, target, capability)


# --- evidence -------------------------------------------------------------------

@router.get("/agents/{agent_id}/evidence")
def list_evidence(
    agent_id: str, event_type: str | None = None, capability: str | None = None,
    visibility: str = Query("public", pattern="^(public|org|private)$"),
    limit: int = Query(100, le=500),
    x_api_key: str | None = Header(default=None),
    auth: OptionalAuth = Depends(), db: Session = Depends(get_db),
):
    """Visibility-enforced evidence read (ADR-012).

    Without the admin key (which stands in for org/platform identity in this
    single-operator deployment), readers see `public` rows only.
    """
    svc = get_services()
    is_admin = x_api_key == get_settings().admin_api_key
    if not is_admin:
        visibility = "public"
    events = svc.evidence.list_for_agent(
        db, agent_id, event_type=event_type, capability=capability,
        visibility_limit=visibility, limit=limit,
    )
    return {"events": [
        {"event_id": e.event_id, "seq": e.seq, "event_type": e.event_type,
         "capability": e.capability, "task_class": e.task_class, "outcome": e.outcome,
         "issuer_type": e.issuer_type, "issuer_id": e.issuer_id,
         "quality_tier": e.quality_tier, "visibility": e.visibility,
         "context": e.context, "event_hash": e.event_hash,
         "prev_event_hash": e.prev_event_hash, "signature": e.signature,
         "created_at": e.created_at.isoformat()}
        for e in events
    ]}


@router.post("/evidence", status_code=201)
def submit_evidence(body: EvidenceSubmit, auth: AdminAuth = Depends(),
                    db: Session = Depends(get_db)):
    """Append signed evidence. Platform-signed by default; counterparty-signed
    when external_public_key+external_signature are provided (verified)."""
    svc = get_services()
    if db.get(Agent, body.agent_id) is None:
        raise HTTPException(status_code=404, detail={
            "error": "not_found", "message": "agent not found"})
    try:
        ev = svc.evidence.append(
            db, agent_id=body.agent_id, event_type=body.event_type,
            issuer_type="counterparty" if body.external_signature else "platform",
            issuer_id=body.issuer_id or "platform", signing_key_id="platform",
            capability=body.capability, task_class=body.task_class,
            outcome=body.outcome, context=body.context,
            quality_tier=body.quality_tier, visibility=body.visibility,
            metadata=body.metadata, corrective_of=body.corrective_of,
            nonce=body.nonce, external_signature=body.external_signature,
            external_public_key=body.external_public_key,
        )
    except EvidenceError as exc:
        raise HTTPException(status_code=400, detail={
            "error": "evidence_rejected", "message": str(exc)}) from exc
    return {"event_id": ev.event_id, "seq": ev.seq, "event_hash": ev.event_hash}
