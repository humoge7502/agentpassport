"""Background jobs: periodic reputation snapshots + security scans (spec §48).

In-process APScheduler (ADR-010); swap for a worker container at scale.
"""

from __future__ import annotations

import logging

from apscheduler.schedulers.background import BackgroundScheduler

from app.config import get_settings

logger = logging.getLogger("agentpassport.jobs")

_scheduler: BackgroundScheduler | None = None


def _snapshot_job(services) -> None:
    from sqlalchemy import select

    from app.models import Agent
    try:
        with services.db.session() as db:
            agents = db.execute(select(Agent).where(Agent.status == "active")).scalars().all()
            for agent in agents:
                services.reputation.snapshot(db, agent.agent_id)
            db.commit()
        logger.info("jobs.reputation_snapshots", extra={"agents": len(agents)})
    except Exception:
        logger.exception("jobs.reputation_snapshots.failed")


def _security_scan_job(services) -> None:
    from sqlalchemy import select

    from app.domain.trust_graph import cluster_security_flags, find_reciprocal_cycles
    from app.models import Agent, TrustRelationship
    try:
        with services.db.session() as db:
            edges = db.execute(select(TrustRelationship)).scalars().all()
            agents = db.execute(select(Agent)).scalars().all()
            edge_dicts = [
                {"issuer": e.issuer_agent_id or e.issuer_org_id or "?",
                 "subject": e.subject_agent_id, "capability": e.capability,
                 "strength": e.strength, "confidence": e.confidence}
                for e in edges
            ]
            cluster_security_flags(
                services.cfg, edge_dicts,
                agent_owners={a.agent_id: a.owner_org_id for a in agents},
                agent_created={a.agent_id: a.created_at for a in agents},
            )
            for pair in find_reciprocal_cycles(edge_dicts):
                services.decisions.record_incident(
                    db, kind="collusion", severity="medium", agent_id=None,
                    detail={"type": "reciprocal_endorsement", "pair": list(pair)},
                )
            db.commit()
    except Exception:
        logger.exception("jobs.security_scan.failed")


def start_scheduler(services) -> BackgroundScheduler:
    global _scheduler
    if _scheduler is not None:
        return _scheduler
    settings_intervals = get_settings()
    _scheduler = BackgroundScheduler(daemon=True)
    _scheduler.add_job(_snapshot_job, "interval",
                       seconds=settings_intervals.jobs_interval_seconds,
                       args=[services], id="reputation-snapshots")
    _scheduler.add_job(_security_scan_job, "interval",
                       seconds=max(60, settings_intervals.jobs_interval_seconds * 2),
                       args=[services], id="security-scan")
    _scheduler.start()
    logger.info("jobs.scheduler_started")
    return _scheduler


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
