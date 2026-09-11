"""Policy engine & trust decision (spec §18/§32/§34/§35, ADR-006).

Decisions are never bare ALLOW/DENY — every decision carries structured,
explainable reasons. Policies are data (rules in DB / config), evaluated in a
fixed pipeline so a future rule language can slot in without touching the
trust engine.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class Decision(str, Enum):
    ALLOW = "ALLOW"
    DENY = "DENY"
    HUMAN_APPROVAL = "HUMAN_APPROVAL"
    REVERIFY = "REVERIFY"
    UNKNOWN = "UNKNOWN"


@dataclass
class Reason:
    code: str
    detail: str
    factor: str = "policy"   # reputation | confidence | security | policy | epoch | graph | delegation

    def to_dict(self) -> dict:
        return {"code": self.code, "detail": self.detail, "factor": self.factor}


@dataclass
class TrustDecision:
    decision: Decision
    agent_id: str
    capability: str
    reasons: list[Reason] = field(default_factory=list)
    score: float | None = None
    confidence: float | None = None
    context: dict[str, Any] = field(default_factory=dict)
    evaluated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    policy_id: str | None = None
    epoch_id: int | None = None
    decision_id: str | None = None

    def to_dict(self) -> dict:
        return {
            "decision": self.decision.value,
            "agent_id": self.agent_id,
            "capability": self.capability,
            "score": self.score,
            "confidence": self.confidence,
            "reasons": [r.to_dict() for r in self.reasons],
            "context": self.context,
            "evaluated_at": self.evaluated_at.isoformat(),
            "policy_id": self.policy_id,
            "epoch_id": self.epoch_id,
            "decision_id": self.decision_id,
        }


@dataclass
class PolicyRule:
    """One evaluatable rule. Fields are optional matchers; all specified
    matchers must hold for the rule to fire.

    Example (spec §69): financial_transaction above a value with low confidence
    → HUMAN_APPROVAL.
    """

    rule_id: str
    name: str
    outcome: Decision
    priority: int = 100
    capability: str | None = None          # exact capability match
    capability_prefix: str | None = None   # e.g. "financial."
    min_transaction_value: float | None = None
    max_transaction_value: float | None = None
    min_score: float | None = None         # fires when score is BELOW this
    min_confidence: float | None = None    # fires when confidence is BELOW this
    max_confidence: float | None = None    # fires when confidence is BELOW this too
    max_security_score: float | None = None  # fires when security dim BELOW this
    risk_classes: list[str] | None = None
    requires_epoch_flag: str | None = None   # e.g. "reverify"

    def matches(self, req: "TrustRequest", rep: dict[str, Any]) -> bool:
        if self.capability is not None and req.capability != self.capability:
            return False
        if (
            self.capability_prefix is not None
            and not req.capability.startswith(self.capability_prefix)
        ):
            return False
        if self.min_transaction_value is not None:
            if (req.transaction_value or 0.0) < self.min_transaction_value:
                return False
        if self.max_transaction_value is not None:
            if (req.transaction_value or 0.0) > self.max_transaction_value:
                return False
        if self.risk_classes and req.risk_class not in self.risk_classes:
            return False
        if self.min_score is not None:
            score = rep.get("score")
            if score is None or score >= self.min_score:
                return False
        if self.min_confidence is not None:
            conf = rep.get("confidence")
            if conf is None or conf >= self.min_confidence:
                return False
        if self.max_confidence is not None:
            conf = rep.get("confidence")
            if conf is None or conf >= self.max_confidence:
                return False
        if self.max_security_score is not None:
            sec = rep.get("security_score")
            if sec is None or sec >= self.max_security_score:
                return False
        if self.requires_epoch_flag and not rep.get("epoch_flags", {}).get(self.requires_epoch_flag):
            return False
        return True

    def to_dict(self) -> dict:
        return {
            "rule_id": self.rule_id, "name": self.name,
            "outcome": self.outcome.value, "priority": self.priority,
        }


@dataclass
class TrustRequest:
    agent_id: str
    capability: str
    risk_class: str = "medium"             # of the capability being requested
    transaction_value: float | None = None
    context: dict[str, Any] = field(default_factory=dict)


def default_policy_rules(cfg: Any) -> list[PolicyRule]:
    """Built-in rule set (configurable thresholds; spec §68)."""
    return [
        PolicyRule(
            rule_id="builtin-security-floor",
            name="Security dimension below floor → DENY",
            outcome=Decision.DENY,
            priority=0,
            max_security_score=float(cfg["security_floor"]),
        ),
        PolicyRule(
            rule_id="builtin-high-value-human",
            name="High-value transaction with weak confidence → HUMAN_APPROVAL",
            outcome=Decision.HUMAN_APPROVAL,
            priority=10,
            min_transaction_value=float(cfg["human_approval_value_threshold"]),
            max_confidence=0.9,
        ),
        PolicyRule(
            rule_id="builtin-reverify-flag",
            name="Epoch flagged for re-verification → REVERIFY",
            outcome=Decision.REVERIFY,
            priority=20,
            requires_epoch_flag="reverify",
        ),
    ]


def evaluate(
    cfg: Any,
    request: TrustRequest,
    reputation: dict[str, Any],   # {"score", "confidence", "security_score", "epoch_flags"}
    extra_rules: list[PolicyRule] | None = None,
    unknown_decision: Decision | None = None,
) -> TrustDecision:
    """Fixed evaluation pipeline. Order:
    1. explicit rules (DB rules then built-ins), lowest priority number first
    2. UNKNOWN reputation handling
    3. threshold gate (score + confidence by risk class)
    4. default ALLOW with recorded basis
    """
    reasons: list[Reason] = []
    decision: Decision | None = None
    policy_id: str | None = None

    rules = sorted(
        list(extra_rules or []) + default_policy_rules(cfg),
        key=lambda r: r.priority,
    )
    for rule in rules:
        if rule.matches(request, reputation):
            decision = rule.outcome
            policy_id = rule.rule_id
            if rule.outcome == Decision.DENY and rule.max_security_score is not None:
                reasons.append(Reason(
                    "security_below_floor",
                    f"security dimension {reputation.get('security_score')} "
                    f"below policy floor {rule.max_security_score}",
                    "security",
                ))
            elif rule.outcome == Decision.HUMAN_APPROVAL:
                reasons.append(Reason(
                    "human_approval_required",
                    f"transaction value {request.transaction_value} exceeds policy "
                    f"threshold with confidence {reputation.get('confidence')}",
                ))
            elif rule.outcome == Decision.REVERIFY:
                reasons.append(Reason(
                    "reverify_required",
                    "trust epoch change requires re-verification before this capability",
                    "epoch",
                ))
            else:
                reasons.append(Reason("rule_matched", rule.name))
            break

    score = reputation.get("score")
    confidence = reputation.get("confidence")

    if decision is None and score is None:
        decision = Decision(unknown_decision or cfg["unknown_decision"])
        policy_id = "builtin-unknown"
        reasons.append(Reason(
            "insufficient_evidence",
            "reputation for this capability is UNKNOWN (insufficient quality evidence)",
            "reputation",
        ))

    if decision is None and score is not None:
        floor = float(cfg["default_score_thresholds"].get(request.risk_class, 65.0))
        conf_floor = float(cfg["default_confidence_floor"].get(request.risk_class, 0.5))
        if score < floor:
            decision = Decision.DENY
            policy_id = "builtin-score-threshold"
            reasons.append(Reason(
                "score_below_threshold",
                f"reputation {score:.1f} below {request.risk_class}-risk threshold {floor:.0f}",
                "reputation",
            ))
        elif confidence is not None and confidence < conf_floor:
            decision = Decision.HUMAN_APPROVAL
            policy_id = "builtin-confidence-floor"
            reasons.append(Reason(
                "confidence_below_floor",
                f"confidence {confidence:.2f} below {request.risk_class}-risk floor {conf_floor:.2f}",
                "confidence",
            ))
        else:
            decision = Decision.ALLOW
            policy_id = "builtin-default"
            reasons.append(Reason(
                "thresholds_met",
                f"score {score:.1f} ≥ {floor:.0f} and confidence "
                f"{confidence:.2f} ≥ {conf_floor:.2f} for {request.risk_class}-risk",
                "reputation",
            ))

    return TrustDecision(
        decision=decision,
        agent_id=request.agent_id,
        capability=request.capability,
        reasons=reasons,
        score=score,
        confidence=confidence,
        context=request.context,
        policy_id=policy_id,
    )
