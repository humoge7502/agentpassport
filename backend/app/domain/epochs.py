"""Trust epochs & reputation inheritance (ADR-007, spec §15/§23).

An epoch closes when the agent's behavioral configuration materially changes
(model, tools, capabilities, permissions, owner). Continuity dimensions are
scored 0..1, combined by a weighted geometric mean, and used to derive an
inheritance factor applied to historical reputation.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.domain.trust_config import TrustConfig


@dataclass
class EpochSnapshot:
    """Behavioral configuration of an agent during an epoch."""

    model_id: str | None = None
    model_family: str | None = None
    owner_org_id: str | None = None
    capabilities: set[str] | None = None
    tools: set[str] | None = None
    permissions: set[str] | None = None

    @staticmethod
    def from_config(d: dict) -> EpochSnapshot:
        return EpochSnapshot(
            model_id=d.get("model_id"),
            model_family=d.get("model_family"),
            owner_org_id=d.get("owner_org_id"),
            capabilities=set(d.get("capabilities", []) or []),
            tools=set(d.get("tools", []) or []),
            permissions=set(d.get("permissions", []) or []),
        )


@dataclass
class ContinuityAssessment:
    dimensions: dict[str, float]          # 0..1 each
    weights: dict[str, float]
    factor: float                          # weighted geometric mean
    reverify: bool
    reasons: list[str]

    def to_dict(self) -> dict:
        return {
            "dimensions": self.dimensions,
            "weights": self.weights,
            "factor": round(self.factor, 4),
            "reverify": self.reverify,
            "reasons": self.reasons,
        }


def _set_continuity(old: set[str] | None, new: set[str] | None) -> float:
    """Jaccard-style continuity with edge cases pinned down."""
    old, new = old or set(), new or set()
    if not old and not new:
        return 1.0
    if not old or not new:
        return 0.0  # appearing-from-nothing / losing everything is a full break
    union = old | new
    return len(old & new) / len(union)


def _model_continuity(old: EpochSnapshot, new: EpochSnapshot) -> float:
    if old.model_id is None and new.model_id is None:
        return 1.0
    if old.model_id == new.model_id:
        return 1.0
    if old.model_family and old.model_family == new.model_family:
        return 0.5  # same family, different version: meaningful but partial
    return 0.0


def _owner_continuity(old: EpochSnapshot, new: EpochSnapshot) -> float:
    return 1.0 if old.owner_org_id == new.owner_org_id else 0.0


def assess_continuity(
    cfg: TrustConfig,
    old: EpochSnapshot,
    new: EpochSnapshot,
    trigger: str,
    security_events_since: int = 0,
    behavior_continuity: float = 1.0,
) -> ContinuityAssessment:
    """Score continuity across dimensions for one transition.

    `trigger` names the change class (model_changed, owner_transferred,
    capability_escalated, ...). `behavior_continuity` comes from the evidence
    stream comparison (service layer).
    """
    dims: dict[str, float] = {
        "identity": 1.0,  # same agent_id by construction; key loss → revocation path
        "ownership": _owner_continuity(old, new),
        "model": _model_continuity(old, new),
        "capabilities": _set_continuity(old.capabilities, new.capabilities),
        "tools": _set_continuity(old.tools, new.tools),
        "permissions": _set_continuity(old.permissions, new.permissions),
        "security": max(0.0, 1.0 - 0.25 * security_events_since),
        "behavior": max(0.0, min(1.0, behavior_continuity)),
    }

    # Security is multiplicative, not averaged: incidents are not one voice
    # among many, they scale down the whole inheritance (floored at 0.1).
    security_multiplier = max(0.1, dims["security"])

    weights = dict(cfg["inheritance_weights"])
    weights.pop("security", None)
    # Trigger emphasis: the change class gets extra weight — the thing that
    # changed cannot be diluted by continuity elsewhere.
    trigger_dim = {
        "model_changed": "model",
        "owner_transferred": "ownership",
        "capability_escalated": "capabilities",
        "tool_changed": "tools",
        "permission_changed": "permissions",
    }.get(trigger)
    if trigger_dim:
        weights[trigger_dim] = weights.get(trigger_dim, 1.0) * 2.0

    # Weighted geometric mean with a per-dimension floor: one collapsed
    # dimension must not annihilate everything, but it must dominate the math.
    floor = 0.10
    factor = 1.0
    wsum = sum(weights.values())
    for dim, w in weights.items():
        v = max(dims.get(dim, 1.0), floor)
        factor *= v ** (w / wsum)
    factor *= security_multiplier

    if trigger == "owner_transferred":
        factor = min(factor, float(cfg["owner_transfer_cap"]))

    reasons: list[str] = []
    for dim, v in sorted(dims.items()):
        if v < 0.5:
            reasons.append(f"low continuity: {dim} ({v:.2f})")

    reverify = (
        factor < float(cfg["reverify_threshold"])
        or trigger in {"owner_transferred", "capability_escalated"}
    )
    return ContinuityAssessment(dims, weights, factor, reverify, reasons)


def inherit_reputation(
    cfg: TrustConfig,
    historical: dict[str, float | None],
    assessment: ContinuityAssessment,
) -> dict[str, float | None]:
    """Apply the inheritance factor to per-capability historical scores.

    UNKNOWN stays UNKNOWN — absence of history is never laundered into trust.
    """
    floor = float(cfg["min_inherited_score"])
    out: dict[str, float | None] = {}
    for cap, score in historical.items():
        if score is None:
            out[cap] = None
        else:
            out[cap] = max(floor, score * assessment.factor)
    return out
