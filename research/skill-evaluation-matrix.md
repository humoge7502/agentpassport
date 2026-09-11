# Skill & Tool Evaluation Matrix

*Evaluated 2026-09-12. Policy (spec §81): inspect → evaluate → test → adapt → document. **No external skill is installed or executed**; guidance principles are distilled into our own design system (ADR-009). Third-party skill installation is treated as a supply-chain concern.*

| Repository | Purpose | Why useful | Quality | Security | License | Maintenance | Compatibility | Recommendation |
|---|---|---|---|---|---|---|---|---|
| [pbakaus/impeccable](https://github.com/pbakaus/impeccable) | Design guidance + deterministic "AI-slop detector" for AI-generated UI (61 rules; grew from Anthropic frontend-design skill) | Anti-pattern detector lists (purple gradients, gray-on-color, card-in-card, bounce easing, tinted neutrals); `/polish`, `/audit`, `/typeset` workflows | High (67.3k★, 1.9k commits, Rust detector engine) | Hybrid repo: ships executables (Rust CLI, hooks, extensions) — do **not** run installers blindly; adopt rule *text* only | Apache-2.0 | Very active, docs site | Framework-agnostic | **ADAPT (guidance only)** |
| [Leonxlnx/taste-skill](https://github.com/Leonxlnx/taste-skill) | "Gives your AI good taste" — SKILL.md guidance for layout/typography/motion/spacing; 3 dials: DESIGN_VARIANCE, MOTION_INTENSITY, VISUAL_DENSITY | Tunable variance/density dials map well to an enterprise dashboard (low variance, high density); editorial-minimalism preset ≈ our target register | High (86.3k★, 154 commits, changelog, v2 in progress) | Guidance markdown + install scripts; scripts not executed | MIT | Active | Framework-agnostic | **ADAPT (guidance only)** |
| [emilkowalski/skills](https://github.com/emilkowalski/skills) | Motion/interaction design judgment from a Vercel/Linear engineer: easing correctness (ease-out for enter), when *not* to animate, borders over fuzzy shadows | Directly encoded in our motion spec (150–250ms ease-out, state-change-driven motion, `prefers-reduced-motion`) | High (37k★) | Guidance markdown only | MIT | Active | Framework-agnostic | **ADAPT (guidance only)** |
| [VoltAgent/awesome-agent-skills](https://github.com/VoltAgent/awesome-agent-skills) | Curated index (1000+ skills) across Anthropic/OpenAI/Google/Vercel/etc. | Discovery surface; confirms `npx skills` cross-vendor ecosystem and quality-standards section | High (34.1k★, 619 commits) | Index only (links) — each linked skill is a separate supply-chain decision | MIT | Very active | n/a | **REFERENCE** |
| `npx skills` CLI ([webrix-ai/add-skills](https://github.com/webrix-ai/add-skills)) | Cross-vendor skill installer (Claude Code, Cursor, Codex, 36+ agents) | Ecosystem context for how skills distribute in 2026 | Widely used | Executes third-party code on install — inherent supply-chain risk | MIT | Active | Multi-agent | **NOT INSTALLED** |

## Distilled design principles adopted into ADR-009

1. **Tint, never pure black/gray** — all neutrals carry hue (our slate-teal base ramp).
2. **No gray text on colored backgrounds**; no purple→blue gradient defaults; no bounce/elastic easing; borders over fuzzy shadows for definition.
3. **Density is a feature** for infra dashboards — high VISUAL_DENSITY, low DESIGN_VARIANCE (consistency), purposeful MOTION_INTENSITY.
4. **Motion correctness:** enter = ease-out, exit = ease-in; animate state changes, not decoration; 150–250ms micro, 300ms+ macro; honor reduced-motion.
5. **Type craft:** tabular numerals for data, tightened tracking at display sizes, restrained scale.
6. **Anti-homogenization:** a distinct accent (Signal Teal), domain-driven hierarchy (trust semantics drive color), not template chrome.
