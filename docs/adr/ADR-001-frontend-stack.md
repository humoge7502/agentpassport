# ADR-001: Frontend Stack

**Status:** Accepted · **Date:** 2026-09-12

## Problem
AgentPassport needs a polished, data-dense trust/security dashboard (10+ screens, charts, an interactive trust graph, responsive, accessible) that a small team can build and maintain.

## Options
1. **Next.js + React + TypeScript** — full framework, SSR/RSC, but heavy for an API-driven internal dashboard; adds server-runtime coupling.
2. **Vite + React + TypeScript + Tailwind CSS** — fast dev loop, SPA is appropriate because the backend is a pure JSON API with no SEO needs; smallest viable surface.
3. SvelteKit / Solid — excellent DX, smaller ecosystems for charting and accessible primitives.

## Decision
**Option 2: Vite + React 18 + TypeScript + Tailwind CSS v4.**

## Reasoning
- The dashboard is auth-gated, API-driven, and behind login — SSR/SEO is irrelevant.
- Tailwind v4's CSS-first `@theme` tokens map directly onto our design-token requirement (ADR-009).
- React's ecosystem gives accessible primitives (Radix-style patterns) and charting options without framework risk.

## Tradeoffs / Consequences
- No SSR → first paint depends on bundle size; mitigate with code-splitting per route and skeleton loading states.
- If a public "passport verification" page is later needed, it can be a small server-rendered page or pre-rendered static route; the design system is portable.
