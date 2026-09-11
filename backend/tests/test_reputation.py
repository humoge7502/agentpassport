"""Reputation engine: decay, weighting, confidence, UNKNOWN, adversarial damping."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.domain.reputation import compute_reputation, dimension_score, diversity_discount
from app.domain.trust_config import TrustConfig

NOW = datetime(2026, 9, 12, tzinfo=timezone.utc)


def ev(event_type, *, days_ago=0, tier="platform_verified", issuer="auditor-1",
       capability="translation"):
    return {
        "event_type": event_type, "capability": capability, "quality_tier": tier,
        "issuer_id": issuer, "created_at": NOW - timedelta(days=days_ago),
    }


def test_no_evidence_is_unknown():
    vec = compute_reputation(TrustConfig(), "a1", "translation", [], NOW)
    o = vec.overall()
    assert o.score is None
    assert o.confidence == 0.0


def test_insufficient_evidence_is_unknown():
    cfg = TrustConfig()
    vec = compute_reputation(cfg, "a1", "translation",
                             [ev("task_completed", days_ago=1)], NOW)
    o = vec.overall()
    assert o.score is None, "one lightweight event must not produce a score"


def test_consistent_success_builds_high_reliability():
    evidence = [ev("task_completed", days_ago=i, issuer=f"iss-{i % 4}") for i in range(30)]
    vec = compute_reputation(TrustConfig(), "a1", "translation", evidence, NOW)
    r = vec.dimensions["reliability"]
    assert r.score is not None and r.score > 85
    assert 0.5 < r.confidence <= 1.0


def test_recent_failure_dominates_stale_success():
    cfg = TrustConfig()
    evidence = ([ev("task_completed", days_ago=200 + i) for i in range(40)]
                + [ev("task_failed", days_ago=1)])
    vec = compute_reputation(cfg, "a1", "translation", evidence, NOW)
    # with 90d half-life, 200-day-old successes decayed heavily
    r = vec.dimensions["reliability"]
    assert r.score is not None
    assert r.score < 70.0


def test_security_violation_crushes_security_dimension():
    evidence = [ev("task_completed", days_ago=i) for i in range(10)]
    evidence.append(ev("security_violation", days_ago=2, tier="platform_verified"))
    vec = compute_reputation(TrustConfig(), "a1", "translation", evidence, NOW)
    assert vec.dimensions["security"].score is not None
    assert vec.dimensions["security"].score < vec.dimensions["reliability"].score


def test_evidence_quality_tiers_change_weight():
    cfg = TrustConfig()
    strong = [ev("task_completed", days_ago=1, tier="independent_audit") for _ in range(6)]
    weak = [ev("task_completed", days_ago=1, tier="self_reported") for _ in range(6)]
    v_strong = compute_reputation(cfg, "a", "translation", strong, NOW)
    v_weak = compute_reputation(cfg, "a", "translation", weak, NOW)
    assert v_strong.overall().confidence > v_weak.overall().confidence


def test_single_issuer_flood_cannot_fake_full_confidence():
    cfg = TrustConfig()
    flood = [ev("task_completed", days_ago=1, issuer="same-issuer") for _ in range(200)]
    diverse = [ev("task_completed", days_ago=i // 7, issuer=f"iss-{i % 6}")
               for i in range(200)]
    v_flood = compute_reputation(cfg, "a", "translation", flood, NOW)
    v_div = compute_reputation(cfg, "a", "translation", diverse, NOW)
    assert v_div.overall().confidence > v_flood.overall().confidence
    assert v_flood.overall().confidence < 0.95


def test_capability_conditioning_separates_dimensions():
    good = [ev("task_completed", capability="translation", days_ago=i) for i in range(20)]
    bad = [ev("security_violation", capability="credential_management", days_ago=i)
           for i in range(5)]
    vec = compute_reputation(TrustConfig(), "a", "translation", good + bad, NOW)
    # translation evidence bucket contains only good events
    assert vec.dimensions["reliability"].score > 80


def test_diversity_discount_bounds():
    cfg = TrustConfig()
    assert diversity_discount(cfg, set(), set(), 0) >= cfg["diversity_min"]
    assert diversity_discount(cfg, {f"i{i}" for i in range(10)},
                              {f"t{i}" for i in range(10)}, 1e9) == 1.0


def test_capability_fallback_to_global():
    evidence = [ev("task_completed", capability=None, days_ago=i) for i in range(20)]
    vecs = __import__("app.domain.reputation", fromlist=["compute_all_capabilities"]) \
        .compute_all_capabilities(TrustConfig(), "a", ["translation"], evidence, NOW)
    assert vecs["_global"].overall().score is not None, \
        "untagged evidence should aggregate into _global (decision path falls back)"
    assert vecs["translation"].overall().score is None, \
        "declared capability with no tagged evidence stays UNKNOWN"
