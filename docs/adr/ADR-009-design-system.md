# ADR-009: Design System & Visual Identity

**Status:** Accepted · **Date:** 2026-09-12

## Problem
The product must read as security/trust infrastructure — precise, credible, calm — not a generic "AI startup gradient" dashboard, and not a clone of any analyzed site (ACM-VIT lessons live in `/research/design-research-acmvit.md`).

## Decision
**Identity: "instrument panel, not poster."** Dark-first, low-chrome, information-forward.

- **Color tokens** (`@theme` in Tailwind v4):
  - Base: near-black slate surfaces (`--color-bg: #0B0F14` family), elevated panels, hairline borders — depth via surface steps, not heavy shadows.
  - Ink: high-contrast off-white text; secondary text ≥ 4.6:1.
  - **Accent: Signal Teal `#2DD4BF`** — used sparingly for interactive/brand moments.
  - **Semantic status scale** (trust semantics, not traffic-light laziness): allow/emerald, condition/amber, deny/rose, unknown/slate-blue, plus a 5-step *trust level* ramp (compromised → verified) mapping score+confidence to color.
- **Typography:** Inter (UI) + JetBrains Mono (ids, hashes, scores). Type scale 12/13/14/16/20/28/40 with deliberate tracking tightening at large sizes. Numbers are tabular everywhere data is compared.
- **Spacing/radius:** 4px base grid; radius scale 6/10/14; consistent 8px gutters in dense tables.
- **Motion:** 150–250ms, ease-out; used for state change, tab transitions, graph physics, and *trust-level changes* (a drop animates — change is the message). All motion honors `prefers-reduced-motion`.
- **Components:** buttons, inputs, tables (dense, sortable), cards, badges/status chips, confidence bars (score + uncertainty always co-displayed), timeline, radar/vector chart, force-graph, command palette, skeletons, empty/error states.
- **Accessibility:** semantic landmarks, visible focus (2px accent outline), full keyboard nav, ARIA only where semantics fall short, charts get table fallbacks.

## Anti-patterns rejected
Glowing gradient hero text, random glassmorphism, decorative confetti animation, alert-fatigue red saturation.
