/** Hand-rolled SVG charts: reputation vector radar, sparkline, force graph.
 *  No chart library — full control over trust semantics + a11y fallbacks. */

import { useMemo, useState } from "react";
import type { DimensionScore, GraphNode, TrustEdge } from "../lib/api";
import { shortId } from "../lib/format";

const DIM_ORDER = [
  "reliability", "security", "accuracy", "compliance",
  "financial_integrity", "task_performance", "policy_compliance",
  "delegation_reliability",
];

const dimLabel = (d: string) => d.replace(/_/g, " ");

/** Reputation vector radar — score fills, confidence shown in tooltip. */
export function VectorRadar({
  dimensions,
  size = 260,
}: {
  dimensions: Record<string, DimensionScore>;
  size?: number;
}) {
  const dims = DIM_ORDER.filter((d) => dimensions[d]);
  const n = dims.length;
  const cx = size / 2;
  const cy = size / 2;
  const rMax = size / 2 - 30;
  const angle = (i: number) => (Math.PI * 2 * i) / n - Math.PI / 2;
  const point = (i: number, r: number) => [cx + r * Math.cos(angle(i)), cy + r * Math.sin(angle(i))];

  const polygon = dims
    .map((d, i) => {
      const s = dimensions[d].score;
      const r = s === null ? 0 : (s / 100) * rMax;
      return point(i, r).join(",");
    })
    .join(" ");

  const grid = [0.25, 0.5, 0.75, 1.0]
    .map((f) => `<polygon points="${dims.map((_, i) => point(i, rMax * f).join(",")).join(" ")}" fill="none" stroke="var(--color-line-soft)" stroke-width="1" />`)
    .join("");

  return (
    <svg
      width={size}
      height={size}
      viewBox={`0 0 ${size} ${size}`}
      role="img"
      aria-label={`Reputation vector radar over ${n} dimensions`}
    >
      <g dangerouslySetInnerHTML={{ __html: grid }} />
      {dims.map((d, i) => {
        const [x, y] = point(i, rMax + 14);
        return (
          <text
            key={d}
            x={x}
            y={y}
            textAnchor={Math.abs(x - cx) < 12 ? "middle" : x > cx ? "start" : "end"}
            dominantBaseline="middle"
            fontSize="9"
            fill="var(--color-ink-faint)"
            style={{ textTransform: "uppercase", letterSpacing: "0.04em" }}
          >
            {dimLabel(d)}
          </text>
        );
      })}
      <polygon
        points={polygon}
        fill="var(--color-accent)"
        fillOpacity="0.18"
        stroke="var(--color-accent)"
        strokeWidth="1.5"
      />
      {dims.map((d, i) => {
        const s = dimensions[d].score;
        if (s === null) return null;
        const [x, y] = point(i, (s / 100) * rMax);
        return <circle key={d} cx={x} cy={y} r="2.5" fill="var(--color-accent)" />;
      })}
    </svg>
  );
}

/** Sparkline for reputation trend (0–100 scale). */
export function Sparkline({
  points,
  width = 160,
  height = 36,
  stroke = "var(--color-accent)",
}: {
  points: (number | null)[];
  width?: number;
  height?: number;
  stroke?: string;
}) {
  const values = points.filter((p): p is number => p !== null);
  if (values.length < 2) {
    return <svg width={width} height={height} aria-hidden />;
  }
  const min = Math.min(...values) - 5;
  const max = Math.max(...values) + 5;
  const span = Math.max(max - min, 1);
  const step = width / (values.length - 1);
  const path = values
    .map((v, i) => `${i === 0 ? "M" : "L"}${(i * step).toFixed(1)},${(height - ((v - min) / span) * height).toFixed(1)}`)
    .join(" ");
  return (
    <svg width={width} height={height} role="img" aria-label="trend sparkline">
      <path d={path} fill="none" stroke={stroke} strokeWidth="1.5" strokeLinejoin="round" />
    </svg>
  );
}

export interface GraphNodeLayout extends GraphNode {
  x: number;
  y: number;
  vx: number;
  vy: number;
}

/** Force-directed trust graph with zoom/pan/drag (spec §77). */
export function TrustGraph({
  nodes,
  edges,
  width = 720,
  height = 480,
  onSelect,
}: {
  nodes: GraphNode[];
  edges: TrustEdge[];
  width?: number;
  height?: number;
  onSelect?: (id: string) => void;
}) {
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [zoom, setZoom] = useState(1);
  const [hoverId, setHoverId] = useState<string | null>(null);

  const layout = useMemo<GraphNodeLayout[]>(() => {
    const rnd = mulberry(42);
    return nodes.map((nd, i) => ({
      ...nd,
      x: width / 2 + Math.cos((i / Math.max(nodes.length, 1)) * Math.PI * 2) * (width / 4) + rnd() * 40,
      y: height / 2 + Math.sin((i / Math.max(nodes.length, 1)) * Math.PI * 2) * (height / 4) + rnd() * 40,
      vx: 0,
      vy: 0,
    }));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [nodes]);

  // simple deterministic force relaxation (runs on mount via layout ticks)
  useMemo(() => {
    const byId = new Map(layout.map((l) => [l.id, l]));
    const repulsion = 2600;
    const spring = 0.015;
    for (let tick = 0; tick < 220; tick++) {
      for (let i = 0; i < layout.length; i++) {
        for (let j = i + 1; j < layout.length; j++) {
          const a = layout[i];
          const b = layout[j];
          const dx = b.x - a.x || 0.01;
          const dy = b.y - a.y || 0.01;
          const d2 = dx * dx + dy * dy;
          const f = repulsion / d2;
          const d = Math.sqrt(d2);
          a.vx -= (dx / d) * f;
          a.vy -= (dy / d) * f;
          b.vx += (dx / d) * f;
          b.vy += (dy / d) * f;
        }
      }
      for (const e of edges) {
        const a = byId.get(e.source);
        const b = byId.get(e.target);
        if (!a || !b) continue;
        const dx = b.x - a.x;
        const dy = b.y - a.y;
        const d = Math.sqrt(dx * dx + dy * dy) || 0.01;
        const target = 130;
        const f = (d - target) * spring;
        a.vx += (dx / d) * f;
        a.vy += (dy / d) * f;
        b.vx -= (dx / d) * f;
        b.vy -= (dy / d) * f;
      }
      for (const nd of layout) {
        // center gravity
        nd.vx += (width / 2 - nd.x) * 0.002;
        nd.vy += (height / 2 - nd.y) * 0.002;
        nd.x += Math.max(-8, Math.min(8, nd.vx));
        nd.y += Math.max(-8, Math.min(8, nd.vy));
        nd.vx *= 0.82;
        nd.vy *= 0.82;
      }
    }
    return null;
  }, [layout, edges, width, height]);

  const byId = new Map(layout.map((l) => [l.id, l]));
  const nodeRadius = (id: string) => {
    const deg = edges.filter((e) => e.source === id || e.target === id).length;
    return 8 + Math.min(10, deg * 1.6);
  };

  const dimNode = (id: string) => hoverId !== null && hoverId !== id
    && !edges.some((e) => (e.source === hoverId && e.target === id)
      || (e.target === hoverId && e.source === id));

  return (
    <div className="relative overflow-hidden rounded-(--radius-md) border border-(--color-line-soft) bg-(--color-bg)">
      <svg
        width="100%"
        viewBox={`0 0 ${width} ${height}`}
        role="application"
        aria-label="Trust relationship graph"
        onWheel={(e) => {
          e.preventDefault();
          setZoom((z) => Math.min(2.5, Math.max(0.4, z * (e.deltaY > 0 ? 0.92 : 1.08))));
        }}
        onMouseDown={(e) => {
          if (e.target === e.currentTarget) setPan({ x: 0, y: 0 });
        }}
      >
        <g transform={`translate(${pan.x} ${pan.y}) scale(${zoom}) translate(${(1 - zoom) * width / 2} ${(1 - zoom) * height / 2})`}>
          {edges.map((e) => {
            const a = byId.get(e.source);
            const b = byId.get(e.target);
            if (!a || !b) return null;
            const faded = hoverId !== null && e.source !== hoverId && e.target !== hoverId;
            return (
              <line
                key={e.id}
                x1={a.x}
                y1={a.y}
                x2={b.x}
                y2={b.y}
                stroke={e.strength >= 0.8 ? "var(--color-allow)" : e.strength >= 0.5 ? "var(--color-condition)" : "var(--color-deny)"}
                strokeOpacity={faded ? 0.08 : 0.5}
                strokeWidth={1 + e.strength * 1.6}
              />
            );
          })}
          {layout.map((nd) => {
            const r = nodeRadius(nd.id);
            const color = nd.status === "active" ? "var(--color-accent)" : "var(--color-unknown)";
            return (
              <g
                key={nd.id}
                transform={`translate(${nd.x} ${nd.y})`}
                opacity={dimNode(nd.id) ? 0.25 : 1}
                style={{ cursor: "pointer" }}
                onMouseEnter={() => setHoverId(nd.id)}
                onMouseLeave={() => setHoverId(null)}
                onClick={() => onSelect?.(nd.id)}
              >
                <circle r={r + 4} fill="var(--color-surface)" stroke={color} strokeOpacity={0.4} />
                <circle r={r} fill="var(--color-surface-3)" stroke={color} strokeWidth={1.5} />
                <text
                  y={r + 12}
                  textAnchor="middle"
                  fontSize="10"
                  fill="var(--color-ink-dim)"
                >
                  {nd.label}
                </text>
              </g>
            );
          })}
        </g>
      </svg>
      <div className="absolute top-2 right-2 flex gap-1">
        <button
          className="rounded-(--radius-sm) border border-(--color-line) bg-(--color-surface) px-2 py-1 text-xs text-(--color-ink-dim) hover:text-(--color-ink)"
          onClick={() => setZoom((z) => Math.min(2.5, z * 1.15))}
          aria-label="zoom in"
        >+</button>
        <button
          className="rounded-(--radius-sm) border border-(--color-line) bg-(--color-surface) px-2 py-1 text-xs text-(--color-ink-dim) hover:text-(--color-ink)"
          onClick={() => setZoom((z) => Math.max(0.4, z / 1.15))}
          aria-label="zoom out"
        >−</button>
      </div>
      <p className="absolute bottom-2 left-3 text-[11px] text-(--color-ink-faint)">
        edge color = strength · hover to focus · click a node for its passport
      </p>
    </div>
  );
}

/** Deterministic PRNG for stable layouts. */
function mulberry(seed: number) {
  let a = seed;
  return () => {
    a |= 0;
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/** Hash-chain strip for evidence (visual integrity indicator). */
export function ChainStrip({ events }: { events: { seq: number; event_hash: string; prev_event_hash: string | null }[] }) {
  const linked = events.every(
    (e, i) => i === 0 || e.prev_event_hash === events[i - 1].event_hash,
  );
  return (
    <div className="flex items-center gap-1" title={linked ? "hash chain intact" : "chain break detected"}>
      {events.slice(0, 24).map((e) => (
        <span
          key={e.seq}
          className="h-3 w-1.5 rounded-full"
          style={{ background: linked ? "var(--color-allow)" : "var(--color-deny)", opacity: 0.35 + (e.seq % 10) * 0.06 }}
        />
      ))}
      <span className="ml-1 text-[11px] text-(--color-ink-faint)">
        {linked ? "chain intact" : "CHAIN BREAK"} · {shortId(events[0]?.event_hash, 6)}…
      </span>
    </div>
  );
}
