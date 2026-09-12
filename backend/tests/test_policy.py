"""Policy engine: contextual decisions, explainability, UNKNOWN handling."""

from __future__ import annotations

from app.domain.policy import Decision, PolicyRule, TrustRequest, evaluate
from app.domain.trust_config import TrustConfig

CFG = TrustConfig()


def rep(score=90.0, conf=0.9, sec=80.0, flags=None):
    return {"score": score, "confidence": conf, "security_score": sec,
            "epoch_flags": flags or {}}


def req(**kw):
    d = {"agent_id": "a1", "capability": "translation", "risk_class": "low"}
    d.update(kw)
    return TrustRequest(**d)


def test_allow_when_thresholds_met():
    d = evaluate(CFG, req(risk_class="low"), rep(score=80, conf=0.5))
    assert d.decision == Decision.ALLOW
    assert any(r.code == "thresholds_met" for r in d.reasons)


def test_deny_below_score_threshold():
    d = evaluate(CFG, req(risk_class="high"), rep(score=60))
    assert d.decision == Decision.DENY
    assert any("below" in r.detail for r in d.reasons)


def test_high_risk_needs_higher_score():
    ok = evaluate(CFG, req(risk_class="high"), rep(score=85, conf=0.9))
    denied = evaluate(CFG, req(risk_class="critical"), rep(score=85, conf=0.9))
    assert ok.decision == Decision.ALLOW
    assert denied.decision == Decision.DENY


def test_unknown_reputation_is_not_allow():
    d = evaluate(CFG, req(), rep(score=None, conf=0.0))
    assert d.decision == Decision.DENY
    assert any(r.code == "insufficient_evidence" for r in d.reasons)


def test_high_value_low_confidence_needs_human():
    d = evaluate(CFG, req(capability="procurement", transaction_value=500000),
                 rep(score=95, conf=0.4))
    assert d.decision == Decision.HUMAN_APPROVAL


def test_security_floor_deny_wins():
    d = evaluate(CFG, req(), rep(score=99, conf=0.99, sec=20.0))
    assert d.decision == Decision.DENY
    assert any(r.factor == "security" for r in d.reasons)


def test_reverify_flag_rule():
    d = evaluate(CFG, req(), rep(score=95, conf=0.95, flags={"reverify": True}))
    assert d.decision == Decision.REVERIFY


def test_custom_rule_first_match_by_priority():
    custom = [
        PolicyRule(rule_id="r2", name="block shopping", outcome=Decision.DENY,
                   priority=5, capability="shopping"),
        PolicyRule(rule_id="r1", name="allow shopping", outcome=Decision.ALLOW,
                   priority=7, capability="shopping"),
    ]
    d = evaluate(CFG, req(capability="shopping"), rep(), extra_rules=custom)
    assert d.decision == Decision.DENY
    assert d.policy_id == "r2"


def test_decision_never_bare():
    """Every decision must carry at least one structured reason (spec §35)."""
    for r in (rep(), rep(score=None, conf=0.0), rep(score=10, conf=0.1, sec=5.0),
              rep(score=95, conf=0.95, flags={"reverify": True})):
        for rc in ("low", "medium", "high", "critical"):
            d = evaluate(CFG, req(risk_class=rc, transaction_value=999999), r)
            assert d.reasons, f"bare decision {d.decision} for {rc}"
