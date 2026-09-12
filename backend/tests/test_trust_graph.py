"""Trust graph: propagation, Sybil damping, collusion, laundering (ADR-008)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.domain.trust_config import TrustConfig
from app.domain.trust_graph import (
    cluster_security_flags,
    damp_edge_weights,
    find_dense_clusters,
    find_reciprocal_cycles,
    lineage_risk,
    propagate_trust,
)

CFG = TrustConfig()
NOW = datetime(2026, 9, 12, tzinfo=UTC)


def edge(a, b, cap="translation", strength=0.9, conf=0.9):
    return {"issuer": a, "subject": b, "capability": cap,
            "strength": strength, "confidence": conf}


def test_direct_trust():
    result = propagate_trust(CFG, [edge("A", "B")], "A", "B", "translation")
    assert result["status"] == "KNOWN"
    assert result["score"] >= 0.85
    assert result["path"] == ["A", "B"]


def test_no_path_is_unknown():
    result = propagate_trust(CFG, [edge("A", "B")], "A", "C", "translation")
    assert result["status"] == "UNKNOWN"
    assert result["score"] is None


def test_propagation_discounts_per_hop():
    edges = [edge("A", "B"), edge("B", "C", strength=1.0, conf=1.0)]
    r1 = propagate_trust(CFG, edges, "A", "B", "translation")
    r2 = propagate_trust(CFG, edges, "A", "C", "translation")
    assert r2["score"] < r1["score"] * 0.99  # gamma discount applied


def test_capability_mismatch_blocks_propagation():
    """A trusts B for procurement; B trusts C for translation ⇒ NOT A→C procurement."""
    edges = [edge("A", "B", cap="procurement"), edge("B", "C", cap="translation")]
    result = propagate_trust(CFG, edges, "A", "C", "procurement")
    assert result["status"] == "UNKNOWN", "trust must not leak across capabilities"


def test_max_depth_bounds_walk():
    edges = [edge("A", "B"), edge("B", "C"), edge("C", "D")]
    result = propagate_trust(CFG, edges, "A", "D", "translation")  # depth 3 > 2
    assert result["status"] == "UNKNOWN"


def test_weak_edges_are_ignored():
    result = propagate_trust(CFG, [edge("A", "B", strength=0.1)], "A", "B", "translation")
    assert result["status"] == "UNKNOWN"


def test_propagated_confidence_bounded_by_weakest_edge():
    edges = [edge("A", "B", conf=0.3), edge("B", "C", conf=1.0)]
    result = propagate_trust(CFG, edges, "A", "C", "translation")
    assert result["confidence"] <= 0.3 + 1e-9


def test_reciprocal_cycles_damped():
    edges = [edge("A", "B"), edge("B", "A")]
    damped = damp_edge_weights(CFG, edges)
    flags = [f for e in damped for f in e["_flags"]]
    assert "reciprocal_cycle" in flags
    assert damped[0]["_damped_strength"] < 0.9


def test_circular_endorsement_pair_has_reduced_influence():
    edges = [edge("A", "B"), edge("B", "A")]
    assert len(find_reciprocal_cycles(edges)) == 1
    damped = damp_edge_weights(CFG, edges)
    assert any(e["_damped_strength"] < e["strength"] for e in damped)


def test_fully_meshed_trio_flagged_as_dense_cluster():
    """A→B→C→A plus reciprocals = dense coordinated cluster (size 3 ≥ min)."""
    edges = [edge("A", "B"), edge("B", "A"), edge("B", "C"), edge("C", "B"),
             edge("C", "A"), edge("A", "C")]
    clusters = find_dense_clusters(CFG, edges)
    assert clusters, "meshed trio must be flagged"


def test_dense_cluster_detection():
    clique = []
    members = ["a", "b", "c", "d", "e"]
    for i, u in enumerate(members):
        for v in members[i + 1:]:
            clique.append(edge(u, v))
            clique.append(edge(v, u))
    clusters = find_dense_clusters(CFG, clique)
    assert clusters and len(clusters[0]) >= 4


def test_sparse_graph_not_flagged():
    sparse = [edge("a", "b"), edge("c", "d"), edge("e", "f")]
    assert find_dense_clusters(CFG, sparse) == []


def test_same_owner_cluster_flagged():
    flags = cluster_security_flags(
        CFG,
        [edge(f"s{i}", "victim") for i in range(4)],
        agent_owners={**{f"s{i}": "org-x" for i in range(4)}, "victim": "org-y"},
        agent_created={f"s{i}": NOW - timedelta(days=30) for i in range(4)},
        now=NOW,
    )
    assert flags.same_owner_clusters


def test_young_issuers_flagged():
    flags = cluster_security_flags(
        CFG, [edge("new1", "victim")],
        agent_owners={"new1": "org-1", "victim": "org-2"},
        agent_created={"new1": NOW - timedelta(days=1), "victim": NOW - timedelta(days=99)},
        now=NOW,
    )
    assert "new1" in flags.young_issuers


def test_laundering_risk_levels():
    clean = lineage_risk(0, False, False, 0.0)
    assert clean["risk"] == "low"
    laundered = lineage_risk(3, True, True, 0.9)
    assert laundered["risk"] == "high" and laundered["reasons"]
    assert "not blacklist" not in laundered  # sanity: text contract unchanged
