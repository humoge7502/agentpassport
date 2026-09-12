# AgentPassport Design System

Identity: **"instrument panel, not poster"** — dark-first, low-chrome, information-forward. Full rationale in [ADR-009](adr/ADR-009-design-system.md); research basis in [research/design-research-acmvit.md](../research/design-research-acmvit.md) and [research/skill-evaluation-matrix.md](../research/skill-evaluation-matrix.md).

## Tokens (frontend/src/index.css, Tailwind v4 `@theme`)

### Surfaces (tinted slate-teal, never pure black)
| Token | Value | Use |
|---|---|---|
| `--color-bg` | `#0B0F14` | app background |
| `--color-surface` | `#10161D` | cards, sidebar |
| `--color-surface-2` | `#161F29` | hover, raised rows |
| `--color-surface-3` | `#1D2833` | skeletons, wells |
| `--color-line` / `-soft` | `#223140` / `#1A2530` | hairline borders |

### Ink
`--color-ink #E6EDF3` · `--color-ink-dim #9DB1C2` (secondary) · `--color-ink-faint #64798C` (tertiary) — all ≥ 4.6:1 on base.

### Accent
Signal Teal `--color-accent #2DD4BF` — interactive/brand moments **only**. It is never a status color.

### Semantic status (trust semantics, not raw traffic lights)
| Token | Meaning |
|---|---|
| `--color-allow #34D399` | ALLOW / verified / healthy |
| `--color-condition #FBBF24` | HUMAN_APPROVAL, REVERIFY / warnings |
| `--color-deny #F87171` | DENY / incidents / broken chains |
| `--color-unknown #7A93A8` | UNKNOWN reputation / neutral states |

### Trust ramp (score+confidence → color)
`trust-1 #F87171` compromised → `trust-2 #FB923C` weak → `trust-3 #FBBF24` developing → `trust-4 #67E8F9` established → `trust-5 #34D399` verified. Applied via `trustLevel()` so color *always* encodes both score and confidence.

## Typography

- **Inter** (UI) + **JetBrains Mono** (ids, hashes, scores, code).
- Scale: 11 / 12 / 13 / 14 / 16 / 20 / 28 / 40. Body 14, dense tables 13, metadata 11–12.
- **Tabular numerals everywhere data is compared** (`.num`, `td`).
- Uppercase + tracking only on 11px labels; never on body copy.

## Spacing, radius, elevation

4px grid; component padding 12/16; gutters 8 in dense tables. Radius 6/10/14 (`--radius-sm|md|lg`). Depth via surface steps + hairlines, not shadows.

## Motion

- Enter/content swap: 150–250 ms **ease-out** (`rise` keyframe).
- Live/attention: soft pulse (loading dots, connecting state).
- Trust-level changes and tab switches animate — **change is the message**; decoration doesn't.
- `prefers-reduced-motion` strips all durations globally (CSS in index.css).

## Components (components/ui.tsx)

`Card/CardHeader` · `Badge` + `DecisionBadge` (ALLOW/HUMAN APPROVAL/REVERIFY/DENY/UNKNOWN) · `ScoreChip` (score + "± confidence" always co-displayed) · `ConfidenceBar` (ARIA meter) · `StatCard` · `Table/Td` (dense, semantic `th` scope) · `Button` (default/primary/danger) · `KeyValue` · `Skeleton` · `EmptyState` · `ErrorState` (role=alert).

Charts (`components/charts.tsx`): `VectorRadar` (8-dimension reputation), `Sparkline`, `TrustGraph` (force-directed, zoom, hover-focus, click→passport), `ChainStrip` (hash-chain integrity indicator).

## Accessibility contract

- Semantic landmarks (`aside/nav/main`, skip-link), `role=tablist` with `aria-selected`, table `caption`+`scope`.
- Visible 2px accent `:focus-visible` outline globally.
- Charts carry `role=img` + aria-labels; confidence bars are ARIA meters.
- Keyboard: all actions are buttons/links; explorer rows are Enter-activatable.
- Color never encodes meaning alone (badges always carry text).
- Motion honors `prefers-reduced-motion`.

## Anti-patterns (rejected, with reasons)

Glowing gradient hero text / random glassmorphism (credibility), card-in-card (noise), hover-only content (a11y, spec lesson from ACM-VIT), bounce/elastic easing (perfectionism ≠ trust), alert-saturation red (fatigue), pure black/gray (deadness).
