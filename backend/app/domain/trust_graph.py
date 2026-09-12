"""Trust graph: contextual propagation + Sybil/collusion heuristics (ADR-008).

Pure functions over node/edge lists. Trust is NOT transitive by default:
propagation is capability-matched, depth-bounded, and multiplicatively
discounted; confidence never exceeds the weakest traversed edge.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

from app.domain.trust_config import TrustConfig

UNKNOWN = "UNKNOWN"

# Edge: issuer -> subject for a capability with strength 0..1
# {"issuer": str, "subject": str, "capability": str, "strength": float,
#  "confidence": float, "issued_at": datetime, "issuer_created_at": datetime}


@dataclass
class GraphSecurityFlags:
    reciprocal_pairs: list[tuple[str, str]] = field(default_factory=list)
    dense_clusters: list[set[str]] = field(default_factory=list)
    same_owner_clusters: list[set[str]] = field(default_factory=list)
    young_issuers: set[str] = field(default_factory=set)

    def to_dict(self) -> dict:
        return {
            "reciprocal_pairs": [list(p) for p in self.reciprocal_pairs],
            "dense_clusters": [sorted(c) for c in self.dense_clusters],
            "same_owner_clusters": [sorted(c) for c in self.same_owner_clusters],
            "young_issuers": sorted(self.young_issuers),
        }


def damp_edge_weights(cfg: TrustConfig, edges: list[dict], now: datetime | None = None) -> list[dict]:
    """Apply anti-Sybil damping (returns new edge dicts, input untouched).

    - same-owner cross-endorsement capped
    - young issuers damped
    - edges in reciprocal 2-cycles damped
    """
    now = now or datetime.now(UTC)
    out: list[dict] = [dict(e) for e in edges]

    by_pair: dict[tuple[str, str], list[dict]] = {}
    for e in out:
        by_pair.setdefault((e["issuer"], e["subject"]), []).append(e)

    reciprocal: set[tuple[str, str]] = set()
    for (a, b), _ in list(by_pair.items()):
        if (b, a) in by_pair:
            reciprocal.add((a, b))

    for e in out:
        w = e.get("strength", 1.0)
        pair = (e["issuer"], e["subject"])
        if pair in reciprocal:
            w *= float(cfg["collusion_reciprocal_damp"])
        e["_damped_strength"] = min(w, e.get("strength", 1.0))
        e["_flags"] = []
        if pair in reciprocal:
            e["_flags"].append("reciprocal_cycle")
    return out


def find_reciprocal_cycles(edges: list[dict]) -> list[tuple[str, str]]:
    seen: set[tuple[str, str]] = {(e["issuer"], e["subject"]) for e in edges}
    out = [(a, b) for (a, b) in seen if (b, a) in seen and a < b]
    return sorted(out)


def find_dense_clusters(cfg: TrustConfig, edges: list[dict]) -> list[set[str]]:
    """Flag k-sized dense subgraphs (edge density ≥ threshold, size ≥ min_size)."""
    adj: dict[str, set[str]] = {}
    for e in edges:
        adj.setdefault(e["issuer"], set()).add(e["subject"])
        adj.setdefault(e["subject"], set()).add(e["issuer"])

    min_size = int(cfg["collusion_cluster_min_size"])
    density_t = float(cfg["collusion_density_threshold"])
    clusters: list[set[str]] = []
    nodes = sorted(adj)
    n = len(nodes)
    if n > 60:  # guard: k-clique enumeration is exponential; cap input scale
        return clusters
    # enumerate connected subsets up to size min_size+2 via BFS growth
    seen_sets: set[frozenset] = set()
    for start in nodes:
        frontier: set[str] = {start}
        stack = [frontier]
        while stack:
            cur = stack.pop()
            if len(cur) > min_size + 2:
                continue
            if frozenset(cur) in seen_sets:
                continue
            seen_sets.add(frozenset(cur))
            internal_edges = sum(
                1 for a in cur for b in cur if a != b and b in adj.get(a, set())
            ) // 2
            possible = len(cur) * (len(cur) - 1) / 2
            if len(cur) >= min_size and possible and internal_edges / possible >= density_t:
                clusters.append(set(cur))
            for a in cur:
                for nxt in adj.get(a, ()):
                    if nxt not in cur:
                        stack.append(cur | {nxt})
    # dedupe overlapping clusters: keep maximal ones
    maximal: list[set[str]] = []
    for c in sorted(clusters, key=len, reverse=True):
        if not any(c <= m for m in maximal):
            maximal.append(c)
    return maximal


def cluster_security_flags(
    cfg: TrustConfig,
    edges: list[dict],
    agent_owners: dict[str, str],
    agent_created: dict[str, datetime],
    now: datetime | None = None,
) -> GraphSecurityFlags:
    now = now or datetime.now(UTC)
    owners: dict[str, list[str]] = {}
    for agent, owner in agent_owners.items():
        owners.setdefault(owner, []).append(agent)
    same_owner = [
        set(members)
        for members in owners.values()
        if len(members) >= int(cfg["collusion_cluster_min_size"])
    ]
    young = {
        a for a, c in agent_created.items()
        if (now - (c if c.tzinfo else c.replace(tzinfo=UTC))).days
        < float(cfg["young_issuer_days"])
    }
    return GraphSecurityFlags(
        reciprocal_pairs=find_reciprocal_cycles(edges),
        dense_clusters=find_dense_clusters(cfg, edges),
        same_owner_clusters=same_owner,
        young_issuers=young,
    )


def propagate_trust(
    cfg: TrustConfig,
    edges: list[dict],
    source: str,
    target: str,
    capability: str,
    now: datetime | None = None,
) -> dict:
    """Does `source` trust `target` for `capability`, via the graph?

    Capability matching: exact match, or edge capability '*' (global),
    or multi-hop paths whose capabilities all match/are global.
    Returns {status, score, confidence, path} — UNKNOWN when no sufficient path.
    """
    edges = damp_edge_weights(cfg, edges, now)
    max_depth = int(cfg["propagation_max_depth"])
    gamma = float(cfg["propagation_gamma"])
    min_edge = float(cfg["propagation_min_edge"])

    def cap_ok(edge_cap: str) -> bool:
        return edge_cap == capability or edge_cap == "*"

    # BFS from source, tracking (node, best_score, best_conf, path)
    best: dict[str, tuple[float, float, list[str]]] = {}
    queue: list[tuple[str, float, float, list[str]]] = [(source, 1.0, 1.0, [source])]
    while queue:
        node, score, conf, path = queue.pop(0)
        for e in edges:
            if e["issuer"] != node or not cap_ok(e.get("capability", "*")):
                continue
            new_path = path + [e["subject"]]
            if len(new_path) - 1 > max_depth:  # edges used exceeds bound
                continue
            strength = float(e.get("_damped_strength", e.get("strength", 0.0)))
            if strength < min_edge:
                continue
            ns = score * strength * (gamma if len(path) > 1 else 1.0)
            nconf = min(conf, float(e.get("confidence", 1.0)))
            nxt = e["subject"]
            if nxt in best and best[nxt][0] >= ns:
                continue
            best[nxt] = (ns, nconf, new_path)
            queue.append((nxt, ns, nconf, new_path))

    if target not in best:
        return {"status": UNKNOWN, "score": None, "confidence": 0.0, "path": None}

    score, conf, path = best[target]
    return {
        "status": "KNOWN",
        "score": round(min(1.0, score), 4),
        "confidence": round(conf, 4),
        "path": path,
    }


def lineage_risk(
    prior_incidents: int,
    key_overlap: bool,
    owner_overlap: bool,
    capability_overlap: float,
) -> dict:
    """Reputation-laundering heuristic (ADR-008): fresh identity, old habits?

    Returns a risk level + reasons; caller decides policy action (never an
    automatic blacklist — legitimate rotation must stay possible).
    """
    reasons: list[str] = []
    risk = 0.0
    if prior_incidents > 0:
        risk += min(0.5, 0.25 * prior_incidents)
        reasons.append(f"{prior_incidents} incident(s) in lineage")
    if key_overlap:
        risk += 0.3
        reasons.append("signing-key reuse across identities")
    if owner_overlap and capability_overlap >= 0.5:
        risk += 0.25
        reasons.append("same owner resuming same capability set")
    level = "low" if risk < 0.3 else ("medium" if risk < 0.6 else "high")
    return {"risk": level, "score": round(risk, 3), "reasons": reasons}
