# Design Research — ACM-VIT Analysis & Dashboard References

*Analyzed 2026-09-12 (live fetch). Used as a source of lessons only — AgentPassport has its own visual identity (ADR-009).*

## ACM-VIT (acmvit.in) — what works

- Real content depth: team grouped by role, projects with live links and repos; projects section is the strongest part.
- Coherent brand personality (dark, terminal-flavored "conspiracy that works") that fits its audience.
- Comprehensive footer sitemap.

## What doesn't / dated / broken

- **DOM duplication** (content rendered twice — hydration/animation-library cloning): bloat, double screen-reader reading — a QA failure.
- **Single-page anchor nav** for deep content (team/blogs/gallery) is a 2016 pattern.
- **Hover-reveal event cards** (cryptic ids hide the actual content behind interaction); image-only blog links with no titles → invisible to crawlers and screen readers.
- **Marquees + word rotators + scroll-jacking** (GSAP/Lenis style) — jank and motion-sickness risk, violates WCAG pause/stop for motion.
- **ALL-CAPS paragraph walls** and stretched letter-spacing titles fight scannability; typos in the hero ("annouce", "forcomputing").
- **Unlabeled form fields**, dead "MORE" link.

## Transferable lessons → AgentPassport

1. Substance before flash: real data density and honest states beat marquee theatrics.
2. Never hide information behind hover-only interaction; never make media the only label.
3. Motion must communicate state, not decorate scroll; always respect reduced-motion (WCAG 2.3.3 / 2.2.2).
4. Ship QA/a11y polish as a requirement, not a later pass.
5. Terminal-flavored dark identity is a *starting* register for us — differentiation comes from execution discipline: tabular numerals, semantic trust colors, calm hierarchy.

## Modern dashboard references (patterns we encode)

- **Linear/Notion register:** editorial minimalism, hairline borders, tinted neutrals, restrained accent — the base register.
- **Datadog/Grafana:** data-dense tables, consistent status color semantics, time-series discipline (axis labels, brushable ranges), tabular numerals everywhere.
- **Vercel dashboard:** calm dark surfaces with stepped elevation, event-timeline patterns (deploy events ≈ our trust epochs/evidence timeline).
- **Stripe dashboard:** explainability pattern — decision surfaces drill down to reasons; we reuse this for "Why was this denied?" (spec §64).

## Concrete token recommendations (adopted in ADR-009)

- Surfaces: `#0B0F14 → #10161D → #161F29` steps; hairline `#1E2A36` borders.
- Text: `#E6EDF3` primary / `#8CA0B3` secondary (≥4.6:1 on base).
- Accent: Signal Teal `#2DD4BF` (interactive/brand only).
- Status: allow `#34D399` · condition `#FBBF24` · deny `#F87171` · unknown `#7A93A8`; trust ramp: compromised → unproven → developing → established → verified.
- Type: Inter (UI) + JetBrains Mono (ids/hashes/scores); 12/13/14/16/20/28/40 scale; tabular-nums on all data.
- Motion: 150–250ms ease-out micro, state-change only, reduced-motion honored.
- Anti-patterns: glowing gradient hero text, glassmorphism, card-in-card, hover-only content, confetti animation, alert-saturation red.
