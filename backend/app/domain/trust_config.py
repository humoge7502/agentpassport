"""Trust configuration: every tunable knob with safe defaults (spec §68).

Nothing in the trust engine may hardcode a policy number — everything reads
from this module, which can be overridden per deployment via TrustConfig.
"""

from __future__ import annotations

from functools import lru_cache

# Dimensions of the multidimensional reputation vector (spec §16).
DIMENSIONS: tuple[str, ...] = (
    "reliability",
    "security",
    "accuracy",
    "compliance",
    "financial_integrity",
    "task_performance",
    "policy_compliance",
    "delegation_reliability",
)

# Evidence quality tiers and their default weights (spec §20).
# Weight is "how much does one such event count as" in evidence-units.
EVIDENCE_QUALITY_WEIGHTS: dict[str, float] = {
    "self_reported": 0.30,
    "counterparty_signed": 0.60,
    "platform_verified": 0.85,
    "independent_audit": 1.00,
    "cryptographic": 1.00,
}

# Event-type → per-dimension signed impact (positive reinforces).
# Impact magnitude is in evidence-units per event (multiplied by quality weight).
EVENT_IMPACTS: dict[str, dict[str, float]] = {
    "task_completed":         {"reliability": +1.0, "task_performance": +0.8},
    "task_failed":            {"reliability": -1.0, "task_performance": -0.6},
    "policy_violation":       {"policy_compliance": -1.5, "compliance": -0.8},
    "security_violation":     {"security": -2.0},
    "audit_passed":           {"compliance": +1.0, "security": +0.5},
    "audit_failed":           {"compliance": -1.2, "security": -0.8},
    "sla_met":                {"reliability": +0.5, "task_performance": +0.3},
    "sla_breached":           {"reliability": -0.8},
    "transaction_completed":  {"financial_integrity": +1.0, "reliability": +0.3},
    "transaction_disputed":   {"financial_integrity": -1.2},
    "human_override":         {},  # recorded, does not move scores by itself
    "delegation_completed":   {"delegation_reliability": +1.0},
    "delegation_failed":      {"delegation_reliability": -1.2},
    "capability_attested":    {"compliance": +0.4},
    "identity_verified":      {"security": +0.5},
    # lifecycle events (model_changed, tool_added, ...) are recorded but carry
    # no direct reputation impact — they act through trust epochs instead.
}


@lru_cache(maxsize=1)
def _default_config() -> dict:
    """Single source of defaults; mutable copies are handed out per instance."""
    return {
        # --- reputation -----------------------------------------------------
        "dimensions": DIMENSIONS,
        "evidence_quality_weights": EVIDENCE_QUALITY_WEIGHTS,
        "event_impacts": EVENT_IMPACTS,
        # prior (Bayesian-flavored anchor): neutral, weak
        "prior_strength": 2.0,       # evidence-units of neutral prior mass
        "prior_mean": 0.5,           # 0..1
        # time decay half-life, days, per dimension (configurable)
        "default_half_life_days": 60.0,
        "half_life_days": {d: 60.0 for d in DIMENSIONS},
        # unknown-threshold: below this effective evidence, reputation is UNKNOWN
        "min_effective_evidence": 1.5,
        # confidence = (1 - 1/(1+n_eff/n_half)) * diversity; n_half ≈ "events for ~71% raw conf"
        "confidence_n_half": 12.0,
        # diversity discount floors: with k distinct issuers/sources and a time
        # span, discount = min(1, floors at 0.35). Implemented in reputation.py.
        "diversity_min": 0.35,
        "diversity_issuer_span": 3.0,    # issuers for full credit
        "diversity_source_span": 3.0,    # quality tiers for full credit
        "diversity_span_days": 3.0,      # activity span (days) for full time credit
        # --- epochs / inheritance (ADR-007) ----------------------------------
        "inheritance_weights": {
            "identity": 1.0,
            "ownership": 1.5,
            "model": 1.2,
            "capabilities": 1.0,
            "tools": 0.8,
            "permissions": 1.0,
            "security": 2.0,
            "behavior": 1.2,
        },
        "min_inherited_score": 0.0,      # floor (0..100) after inheritance
        "reverify_threshold": 0.60,      # below this factor → REVERIFY recommended
        "owner_transfer_cap": 0.75,      # owner change: hard cap on inherited factor
        # --- trust propagation (ADR-008) --------------------------------------
        "propagation_max_depth": 2,
        "propagation_gamma": 0.5,        # discount per hop
        "propagation_min_edge": 0.30,    # edges below this strength are ignored
        # --- sybil / collusion (ADR-008) --------------------------------------
        "young_issuer_days": 14.0,       # issuers younger than this are damped
        "young_issuer_damp": 0.4,        # endorsement weight multiplier
        "same_owner_endorsement_cap": 0.25,  # cap on cross-endorsement within one owner
        "collusion_reciprocal_damp": 0.5,    # damp edges participating in 2-cycles
        "collusion_cluster_min_size": 3,     # dense cluster flag size
        "collusion_density_threshold": 0.75, # subgraph edge density considered dense
        # --- decisions / policy (ADR-006/§18) ----------------------------------
        "default_score_thresholds": {    # per decision, min reputation score
            "low": 50.0, "medium": 65.0, "high": 80.0, "critical": 90.0,
        },
        "default_confidence_floor": {    # min confidence by risk class
            "low": 0.30, "medium": 0.50, "high": 0.70, "critical": 0.85,
        },
        "security_floor": 40.0,          # security dimension below this → DENY
        "unknown_decision": "DENY",      # what UNKNOWN reputation yields under policy
        "human_approval_value_threshold": 100000.0,  # value above → HUMAN_APPROVAL
    }


class TrustConfig:
    """Mutable view over the defaults; used by the policy engine and tests."""

    def __init__(self, overrides: dict | None = None):
        base = _default_config()
        self._data: dict = {k: (dict(v) if isinstance(v, dict) else v) for k, v in base.items()}
        if overrides:
            for k, v in overrides.items():
                if isinstance(v, dict) and isinstance(self._data.get(k), dict):
                    self._data[k].update(v)
                else:
                    self._data[k] = v

    def __getitem__(self, key: str):
        return self._data[key]

    def get(self, key: str, default=None):
        return self._data.get(key, default)

    def as_dict(self) -> dict:
        return self._data


def quality_weight(cfg: TrustConfig, tier: str) -> float:
    weights = cfg["evidence_quality_weights"]
    return float(weights.get(tier, 0.30))
