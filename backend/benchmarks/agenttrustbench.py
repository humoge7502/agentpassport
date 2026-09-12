"""AgentTrustBench (spec §51/§85/§86).

Deterministic synthetic scenarios evaluating the trust engine against
adversarial behavior. Metrics: false trust, false distrust, precision/recall
for attack detection, confidence calibration probes, decision latency.

Run:  python -m benchmarks.agenttrustbench [scenarios...]
"""

from __future__ import annotations

import json
import random
import statistics
import sys
import tempfile
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.domain.policy import Decision, TrustRequest  # noqa: E402
from app.services import build_services  # noqa: E402

NOW = datetime(2026, 9, 12, tzinfo=timezone.utc)


@dataclass
class ScenarioResult:
    scenario: str
    metrics: dict = field(default_factory=dict)
    notes: str = ""


def _services(seed: int = 42):
    import random as _r
    _r.seed(seed)
    tmp = tempfile.mkdtemp(prefix="ap-bench-")
    svc = build_services(database_url=f"sqlite:///{tmp}/bench.db")
    from app.services_identity import KeyService
    from app.services_evidence import EvidenceService
    from app.services_decision import ReputationService, TrustDecisionService
    from app.services_delegation import DelegationService
    from app.services_identity import IdentityService
    svc.keys = KeyService(str(Path(tmp) / "keys"))
    svc.identity = IdentityService(svc.cfg, svc.keys)
    svc.evidence = EvidenceService(svc.cfg, svc.keys)
    svc.reputation = ReputationService(svc.cfg, svc.evidence)
    svc.decisions = TrustDecisionService(svc.cfg, svc.reputation, svc.evidence)
    svc.delegations = DelegationService(svc.cfg, svc.decisions, svc.evidence)
    svc.db.create_all()
    return svc


def _feed(svc, db, agent_id, capability, successes, fails=0, *, days_span=45,
          tiers=("platform_verified", "counterparty_signed", "independent_audit"),
          issuers=4, tag=""):
    for i in range(successes + fails):
        etype = "task_completed" if i < successes else "task_failed"
        svc.evidence.append(
            db, agent_id=agent_id, event_type=etype, capability=capability,
            issuer_type="platform", issuer_id=f"observer-{i % issuers}",
            signing_key_id="platform", quality_tier=tiers[i % len(tiers)],
            nonce=f"bench-{tag}-{agent_id[:8]}-{i}",
            created_at=NOW - timedelta(days=(i % days_span)))


def _req(agent_id, capability, risk="medium", value=None):
    return TrustRequest(agent_id=agent_id, capability=capability, risk_class=risk,
                        transaction_value=value)


# --- scenarios ----------------------------------------------------------------

def scenario_honest_agents(svc, db) -> ScenarioResult:
    """Honest high-performers must be ALLOWed; new agents must not be."""
    r = ScenarioResult("honest_agents")
    honest = svc.identity.create_agent(db, "org-honest", "Honest-1",
                                       capabilities=["translation"])
    _feed(svc, db, honest.agent_id, "translation", 40, 1, tag="h")
    db.commit()
    decision = svc.decisions.evaluate_request(db, _req(honest.agent_id, "translation"))
    r.metrics["honest_allowed"] = decision.decision == Decision.ALLOW

    newbie = svc.identity.create_agent(db, "org-honest", "Newbie-1",
                                       capabilities=["translation"])
    _feed(svc, db, newbie.agent_id, "translation", 1, 0, tag="n")
    db.commit()
    d2 = svc.decisions.evaluate_request(db, _req(newbie.agent_id, "translation"))
    r.metrics["newbie_not_allowed"] = d2.decision != Decision.ALLOW
    r.notes = ("honest → ALLOW; 1-event newbie → " + d2.decision.value)
    return r


def scenario_reputation_inflation(svc, db) -> ScenarioResult:
    """Self-reported flood must not outperform quality evidence."""
    r = ScenarioResult("reputation_inflation")
    flooder = svc.identity.create_agent(db, "org-sybil", "Flooder",
                                        capabilities=["research"])
    for i in range(300):
        svc.evidence.append(
            db, agent_id=flooder.agent_id, event_type="task_completed",
            capability="research", issuer_type="self", issuer_id="self",
            signing_key_id="platform", quality_tier="self_reported",
            nonce=f"self-{i}", created_at=NOW - timedelta(days=0))
    quality = svc.identity.create_agent(db, "org-honest", "Quality",
                                        capabilities=["research"])
    _feed(svc, db, quality.agent_id, "research", 30, 1, tag="q")
    db.commit()
    f = svc.reputation.for_agent(db, flooder.agent_id, [])["_global"]["dimensions"]
    q = svc.reputation.for_agent(db, quality.agent_id, [])["_global"]["dimensions"]
    r.metrics["flood_confidence"] = round(f["reliability"]["confidence"], 3)
    r.metrics["quality_confidence"] = round(q["reliability"]["confidence"], 3)
    r.metrics["flood_confidence_below_quality"] = (
        f["reliability"]["confidence"] < q["reliability"]["confidence"])
    r.notes = "300 self-reported events must not out-certain 30 quality events"
    return r


def scenario_sybil_endorsement_boost(svc, db) -> ScenarioResult:
    """Mutual endorsement ring gains less than honest diverse attestation."""
    r = ScenarioResult("sybil_endorsement_boost")
    from app.models import TrustRelationship, new_id
    ring = [svc.identity.create_agent(db, "org-sybil", f"Ring-{i}",
                                      capabilities=["research"]) for i in range(5)]
    # pure cycle: each node endorses only its neighbors (tests hop discounting)
    n = len(ring)
    for i in range(n):
        for j in ((i + 1) % n, (i - 1) % n):
            db.add(TrustRelationship(
                relationship_id=new_id(), issuer_agent_id=ring[i].agent_id,
                subject_agent_id=ring[j].agent_id, capability="research",
                strength=1.0, confidence=1.0))
    honest_pair = [svc.identity.create_agent(db, "org-honest", f"HP-{i}",
                                             capabilities=["research"]) for i in range(2)]
    db.add(TrustRelationship(relationship_id=new_id(),
                             issuer_agent_id=honest_pair[0].agent_id,
                             subject_agent_id=honest_pair[1].agent_id,
                             capability="research", strength=0.8, confidence=0.8))
    db.commit()
    from app.domain.trust_graph import damp_edge_weights
    edges = [{"issuer": e.issuer_agent_id, "subject": e.subject_agent_id,
              "capability": e.capability, "strength": e.strength,
              "confidence": e.confidence}
             for e in db.query(TrustRelationship).all()]
    damped = damp_edge_weights(svc.cfg, edges)
    reciprocal_damped = [e for e in damped
                         if e["_damped_strength"] < e["strength"]]
    r.metrics["edges_damped"] = len(reciprocal_damped)
    r.metrics["reciprocal_damp_active"] = len(reciprocal_damped) > 0
    # 2-hop propagation through the ring is heavily discounted
    from app.domain.trust_graph import propagate_trust
    ring_ids = [a.agent_id for a in ring]
    prop = propagate_trust(svc.cfg, damped, ring_ids[0], ring_ids[2], "research")
    r.metrics["ring_propagated_score"] = prop["score"]
    r.metrics["ring_propagation_discounted"] = (prop["score"] or 1.0) < 0.5
    return r


def scenario_model_change_trust_drop(svc, db) -> ScenarioResult:
    r = ScenarioResult("model_change_trust_drop")
    agent = svc.identity.create_agent(db, "org-honest", "Changer",
                                      capabilities=["translation"])
    _feed(svc, db, agent.agent_id, "translation", 35, 1, tag="mc")
    db.commit()
    before = svc.decisions.evaluate_request(db, _req(agent.agent_id, "translation"))
    svc.identity.update_agent(db, agent, trigger="model_changed",
                              model_id="new-model", model_family="new")
    db.commit()
    after = svc.decisions.evaluate_request(db, _req(agent.agent_id, "translation"))
    r.metrics["before"] = before.decision.value
    r.metrics["after"] = after.decision.value
    r.metrics["trust_gated_after_change"] = after.decision != Decision.ALLOW
    return r


def scenario_confidence_calibration(svc, db) -> ScenarioResult:
    """Confidence must increase with evidence quantity, quality, diversity."""
    r = ScenarioResult("confidence_calibration")
    small = svc.identity.create_agent(db, "org-c", "Small", capabilities=["t"])
    _feed(svc, db, small.agent_id, "t", 5, tag="s")
    mid = svc.identity.create_agent(db, "org-c", "Mid", capabilities=["t"])
    _feed(svc, db, mid.agent_id, "t", 25, tag="m")
    big = svc.identity.create_agent(db, "org-c", "Big", capabilities=["t"])
    _feed(svc, db, big.agent_id, "t", 80, tag="b")
    db.commit()

    def conf(agent):
        d = svc.reputation.for_agent(db, agent.agent_id, [])["_global"]["dimensions"]
        return d["reliability"]["confidence"]
    c_small, c_mid, c_big = conf(small), conf(mid), conf(big)
    r.metrics["confidence_small"] = round(c_small, 3)
    r.metrics["confidence_mid"] = round(c_mid, 3)
    r.metrics["confidence_big"] = round(c_big, 3)
    r.metrics["monotonic_in_evidence"] = c_small < c_mid < c_big
    r.metrics["bounded"] = c_big <= 1.0
    return r


def scenario_contextual_decay(svc, db) -> ScenarioResult:
    """Stale-good + recent-bad must score below fresh-good."""
    r = ScenarioResult("contextual_decay")
    stale = svc.identity.create_agent(db, "org-d", "Stale", capabilities=["t"])
    for i in range(30):
        svc.evidence.append(
            db, agent_id=stale.agent_id, event_type="task_completed", capability="t",
            issuer_type="platform", issuer_id=f"o-{i % 3}", signing_key_id="platform",
            quality_tier="platform_verified", nonce=f"stale-{i}",
            created_at=NOW - timedelta(days=400 + i))
    fresh = svc.identity.create_agent(db, "org-d", "Fresh", capabilities=["t"])
    for i in range(30):
        svc.evidence.append(
            db, agent_id=fresh.agent_id, event_type="task_completed", capability="t",
            issuer_type="platform", issuer_id=f"o-{i % 3}", signing_key_id="platform",
            quality_tier="platform_verified", nonce=f"fresh-{i}",
            created_at=NOW - timedelta(days=i % 20))
    db.commit()
    s = svc.reputation.for_agent(db, stale.agent_id, [])["_global"]["dimensions"]
    f = svc.reputation.for_agent(db, fresh.agent_id, [])["_global"]["dimensions"]
    s_conf = s["reliability"]["confidence"]
    f_conf = f["reliability"]["confidence"]
    r.metrics["stale_confidence"] = round(s_conf, 3)
    r.metrics["fresh_confidence"] = round(f_conf, 3)
    r.metrics["stale_below_fresh"] = s_conf < f_conf
    return r


def scenario_decision_latency(svc, db) -> ScenarioResult:
    """p95 trust-evaluation latency on a warm agent with 100+ evidence rows."""
    r = ScenarioResult("decision_latency")
    agent = svc.identity.create_agent(db, "org-perf", "Perf", capabilities=["t"])
    _feed(svc, db, agent.agent_id, "t", 120, tag="p")
    db.commit()
    latencies = []
    for _ in range(50):
        start = time.perf_counter()
        svc.decisions.evaluate_request(db, _req(agent.agent_id, "t"))
        latencies.append((time.perf_counter() - start) * 1000)
    r.metrics["mean_ms"] = round(statistics.mean(latencies), 2)
    r.metrics["p95_ms"] = round(sorted(latencies)[int(0.95 * len(latencies))], 2)
    r.metrics["max_ms"] = round(max(latencies), 2)
    r.notes = "target: p95 < 50 ms on warm SQLite (heuristic gate)"
    return r


SCENARIOS = {
    "honest_agents": scenario_honest_agents,
    "reputation_inflation": scenario_reputation_inflation,
    "sybil_endorsement_boost": scenario_sybil_endorsement_boost,
    "model_change_trust_drop": scenario_model_change_trust_drop,
    "confidence_calibration": scenario_confidence_calibration,
    "contextual_decay": scenario_contextual_decay,
    "decision_latency": scenario_decision_latency,
}


def run_bench(selected: list[str] | None = None, out_dir: Path | None = None) -> list[ScenarioResult]:
    names = selected or list(SCENARIOS)
    results: list[ScenarioResult] = []
    for name in names:
        svc = _services()
        db = svc.db.session()
        try:
            results.append(SCENARIOS[name](svc, db))
        finally:
            db.close()
    out_dir = out_dir or Path(__file__).resolve().parents[1] / "benchmarks" / "results"
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = [{"scenario": r.scenario, "metrics": r.metrics, "notes": r.notes}
               for r in results]
    (out_dir / "latest-bench.json").write_text(json.dumps(payload, indent=2))
    return results


if __name__ == "__main__":
    selected = sys.argv[1:] or None
    results = run_bench(selected)
    print("\nAgentTrustBench results")
    print("=" * 60)
    for r in results:
        print(f"\n{r.scenario}")
        for k, v in r.metrics.items():
            print(f"  {k:36s} {v}")
        if r.notes:
            print(f"  note: {r.notes}")
