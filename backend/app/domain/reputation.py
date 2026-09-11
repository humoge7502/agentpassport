"""Reputation engine (ADR-006).

Pure functions over evidence records. No DB access here — the service layer
feeds evidence in, this module computes vectors. Every knob comes from
TrustConfig.

Evidence input shape (dict):
    {
      "event_id", "event_type", "capability", "quality_tier",
      "issuer_type", "issuer_id", "created_at" (aware datetime), "outcome" ...
    }
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timezone

from app.domain import trust_config as tc
from app.domain.trust_config import DIMENSIONS, TrustConfig

UNKNOWN = "UNKNOWN"


def _as_aware(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


@dataclass
class DimensionScore:
    score: float | None      # 0..100 or None for UNKNOWN
    confidence: float        # 0..1
    n_eff: float             # effective (quality+decay weighted) evidence size
    positive: float
    negative: float
    evidence_count: int

    def to_dict(self) -> dict:
        return {
            "score": self.score, "confidence": self.confidence,
            "n_eff": self.n_eff, "positive": self.positive,
            "negative": self.negative, "evidence_count": self.evidence_count,
        }


@dataclass
class ReputationVector:
    agent_id: str
    capability: str
    computed_at: datetime
    dimensions: dict[str, DimensionScore] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "agent_id": self.agent_id,
            "capability": self.capability,
            "computed_at": self.computed_at.isoformat(),
            "dimensions": {k: v.to_dict() for k, v in self.dimensions.items()},
        }

    def overall(self) -> DimensionScore:
        """Aggregate across dimensions: weighted by evidence mass, UNKNOWN-aware."""
        known = [(d, s) for d, s in self.dimensions.items() if s.score is not None]
        if not known:
            return DimensionScore(None, 0.0, 0.0, 0.0, 0.0, 0)
        mass = sum(s.n_eff for _, s in known) or 1e-9
        score = sum((s.score or 0.0) * s.n_eff for _, s in known) / mass
        conf = min(s.confidence for _, s in known)  # bounded by weakest dimension
        n_eff = sum(s.n_eff for _, s in known)
        pos = sum(s.positive for _, s in known)
        neg = sum(s.negative for _, s in known)
        count = sum(s.evidence_count for _, s in known)
        return DimensionScore(score, conf, n_eff, pos, neg, count)


def diversity_discount(
    cfg: TrustConfig,
    issuers: set[str],
    tiers: set[str],
    time_span: float,
) -> float:
    """Confidence multiplier: many distinct issuers/tiers over time = full credit.

    A flood of same-issuer same-tier events cannot manufacture certainty.
    """
    issuer_frac = min(1.0, len(issuers) / cfg["diversity_issuer_span"])
    tier_frac = min(1.0, len(tiers) / cfg["diversity_source_span"])
    span_frac = min(1.0, time_span / 86400.0 / float(cfg["diversity_span_days"]))
    base = 0.55 * issuer_frac + 0.30 * tier_frac + 0.15 * span_frac
    return max(float(cfg["diversity_min"]), base)


def dimension_score(
    cfg: TrustConfig,
    evidence: list[dict],
    dimension: str,
    now: datetime,
) -> DimensionScore:
    """Compute one dimension from evidence impacting it.

    score = 100 · (w⁺ + s·prior_mean) / (w⁺ + w⁻ + s)
    confidence = (1 − 1/(1 + n_eff/n_half)) · diversity
    """
    half_life = float(cfg["half_life_days"].get(dimension, cfg["default_half_life_days"]))
    impacts = cfg["event_impacts"]
    q_weights = cfg["evidence_quality_weights"]

    pos = neg = n_eff = 0.0
    issuers: set[str] = set()
    tiers: set[str] = set()
    timestamps: list[datetime] = []
    count = 0

    for ev in evidence:
        impact_map = impacts.get(ev.get("event_type", ""), {})
        impact = impact_map.get(dimension)
        if not impact:
            continue
        created = _as_aware(ev["created_at"])
        age_days = max(0.0, (_as_aware(now) - created).total_seconds() / 86400.0)
        decay = math.exp(-math.log(2) * age_days / max(half_life, 1e-6))
        q = float(q_weights.get(ev.get("quality_tier", "self_reported"), 0.30))
        w = abs(impact) * q * decay
        n_eff += w
        if impact > 0:
            pos += w
        else:
            neg += w
        issuers.add(str(ev.get("issuer_id", ev.get("issuer_type", "?"))))
        tiers.add(ev.get("quality_tier", "self_reported"))
        timestamps.append(created)
        count += 1

    if n_eff < float(cfg["min_effective_evidence"]):
        return DimensionScore(None, 0.0, n_eff, pos, neg, count)

    prior = float(cfg["prior_strength"])
    mean01 = (pos + prior * float(cfg["prior_mean"])) / (pos + neg + prior)
    raw_conf = 1.0 - 1.0 / (1.0 + n_eff / float(cfg["confidence_n_half"]))
    span = (max(timestamps) - min(timestamps)).total_seconds() if len(timestamps) > 1 else 0.0
    conf = raw_conf * diversity_discount(cfg, issuers, tiers, span)
    return DimensionScore(100.0 * mean01, conf, n_eff, pos, neg, count)


def compute_reputation(
    cfg: TrustConfig,
    agent_id: str,
    capability: str,
    evidence: list[dict],
    now: datetime | None = None,
) -> ReputationVector:
    """Full capability-conditioned reputation vector R(agent, capability, time)."""
    now = _as_aware(now or datetime.now(timezone.utc))
    vec = ReputationVector(agent_id=agent_id, capability=capability, computed_at=now)
    for dim in cfg["dimensions"]:
        vec.dimensions[dim] = dimension_score(cfg, evidence, dim, now)
    return vec


def compute_all_capabilities(
    cfg: TrustConfig,
    agent_id: str,
    capabilities: list[str],
    evidence: list[dict],
    now: datetime | None = None,
) -> dict[str, ReputationVector]:
    """R(agent, capability, time) per declared capability + a `_global` fallback.

    Evidence not tagged with a declared capability contributes to `_global`.
    """
    now = _as_aware(now or datetime.now(timezone.utc))
    buckets: dict[str, list[dict]] = {cap: [] for cap in capabilities}
    buckets["_global"] = []
    for ev in evidence:
        cap = ev.get("capability")
        if cap in buckets:
            buckets[cap].append(ev)
        else:
            buckets["_global"].append(ev)
    return {
        cap: compute_reputation(cfg, agent_id, cap, evs, now)
        for cap, evs in buckets.items()
    }


# --- simulation-facing helpers (benchmarks/simulations) ----------------------

def score_with_metadata(vec: ReputationVector) -> dict:
    """Convenience: overall score dict with explicit UNKNOWN handling."""
    o = vec.overall()
    return {
        "score": None if o.score is None else round(o.score, 2),
        "confidence": round(o.confidence, 4),
        "evidence_count": o.evidence_count,
        "status": UNKNOWN if o.score is None else "KNOWN",
    }


__all__ = [
    "DIMENSIONS", "UNKNOWN", "ReputationVector", "DimensionScore",
    "compute_reputation", "compute_all_capabilities", "dimension_score",
    "diversity_discount", "score_with_metadata",
]
