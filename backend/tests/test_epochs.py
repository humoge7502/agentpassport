"""Trust epochs, continuity assessment, and reputation inheritance (ADR-007)."""

from __future__ import annotations

from app.domain.epochs import EpochSnapshot, assess_continuity, inherit_reputation
from app.domain.trust_config import TrustConfig

CFG = TrustConfig()


def base_snapshot(**kw):
    d = {
        "model_id": "gpt-x-1", "model_family": "gpt-x",
        "owner_org_id": "org-a",
        "capabilities": {"translation"}, "tools": {"t1", "t2"},
        "permissions": {"read"},
    }
    d.update(kw)
    return EpochSnapshot(**d)


def test_no_change_is_full_continuity():
    old = base_snapshot()
    new = base_snapshot()
    a = assess_continuity(CFG, old, new, "model_changed")
    assert a.factor > 0.99
    assert not a.reverify


def test_model_change_reduces_but_keeps_partial_continuity():
    a = assess_continuity(CFG, base_snapshot(), base_snapshot(model_id="gpt-y-9",
                                                              model_family="gpt-y"),
                          "model_changed")
    assert 0.3 < a.factor < 0.95
    assert a.dimensions["model"] == 0.0


def test_same_family_version_bump_is_gentler():
    same_family = assess_continuity(
        CFG, base_snapshot(), base_snapshot(model_id="gpt-x-2"), "model_changed")
    diff_family = assess_continuity(
        CFG, base_snapshot(), base_snapshot(model_id="llama-9", model_family="llama"),
        "model_changed")
    assert same_family.factor > diff_family.factor
    assert same_family.dimensions["model"] == 0.5


def test_owner_transfer_caps_inheritance_and_requires_reverify():
    a = assess_continuity(CFG, base_snapshot(), base_snapshot(owner_org_id="org-b"),
                          "owner_transferred")
    assert a.factor <= CFG["owner_transfer_cap"]
    assert a.reverify


def test_capability_escalation_penalizes():
    a = assess_continuity(CFG, base_snapshot(),
                          base_snapshot(capabilities={"translation", "financial_transaction"}),
                          "capability_escalated")
    assert a.dimensions["capabilities"] < 1.0


def test_security_events_collapse_continuity():
    a = assess_continuity(CFG, base_snapshot(), base_snapshot(), "model_changed",
                          security_events_since=5)
    assert a.dimensions["security"] == 0.0
    # geometric mean: security collapse dominates (weight 2.0)
    b = assess_continuity(CFG, base_snapshot(), base_snapshot(), "model_changed")
    assert a.factor < b.factor * 0.5


def test_inheritance_applies_factor_per_capability():
    hist = {"translation": 90.0, "code_execution": 40.0, "new_cap": None}
    a = assess_continuity(CFG, base_snapshot(), base_snapshot(model_id="other"),
                          "model_changed")
    inherited = inherit_reputation(CFG, hist, a)
    assert inherited["translation"] < 90.0
    assert inherited["code_execution"] < 40.0
    assert inherited["new_cap"] is None, "UNKNOWN must stay UNKNOWN through inheritance"
