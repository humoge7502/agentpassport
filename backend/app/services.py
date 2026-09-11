"""Service registry: builds the service graph once per process."""

from __future__ import annotations

from dataclasses import dataclass

from app.config import get_settings
from app.db import Database
from app.domain.trust_config import TrustConfig
from app.services_decision import ReputationService, TrustDecisionService
from app.services_delegation import DelegationService
from app.services_evidence import EvidenceService
from app.services_identity import IdentityService, KeyService


@dataclass
class Services:
    cfg: TrustConfig
    db: Database
    keys: KeyService
    identity: IdentityService
    evidence: EvidenceService
    reputation: ReputationService
    decisions: TrustDecisionService
    delegations: DelegationService


_services: Services | None = None


def build_services(database_url: str | None = None) -> Services:
    global _services
    if _services is not None and database_url is None:
        return _services
    settings = get_settings()
    cfg = TrustConfig()
    db = Database(database_url or settings.database_url)
    keys = KeyService(settings.secret_keys_path)
    identity = IdentityService(cfg, keys)
    evidence = EvidenceService(cfg, keys)
    reputation = ReputationService(cfg, evidence)
    decisions = TrustDecisionService(cfg, reputation, evidence)
    delegations = DelegationService(cfg, decisions, evidence_service=evidence)
    svc = Services(cfg, db, keys, identity, evidence, reputation, decisions, delegations)
    if database_url is None:
        _services = svc
    return svc


def get_services() -> Services:
    global _services
    if _services is None:
        _services = build_services()
        _services.db.create_all()
    return _services
