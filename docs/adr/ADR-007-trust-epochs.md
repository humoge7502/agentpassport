# ADR-007: Trust Epochs & Reputation Inheritance

**Status:** Accepted · **Date:** 2026-09-12

## Problem
Agent evolution (model swap, tool change, capability grant, owner transfer) must not silently carry historical trust. Yet hard-zeroing on every change would make the system unusable.

## Decision
**Trust epoch** = a period during which the agent's *behavioral configuration* (model, tools, capabilities, permissions, owner) is materially unchanged. Any such change closes epoch N, opens epoch N+1, emits evidence events (`model_changed`, `tool_added`, …), and triggers a **continuity assessment**:

| continuity dimension | compares |
|---|---|
| identity | same agent_id + key continuity |
| ownership | same owning org |
| model | model family/version similarity |
| capabilities | set overlap |
| tools | set overlap |
| permissions | set overlap/delta |
| security | security-relevant events since epoch start |
| behavior | evidence-stream continuity (volume, task-class mix, outcome rate shift) |

Each dimension yields a 0–1 continuity score with an explicit, explainable contribution. The **inheritance factor** is the weighted geometric mean of dimension scores (weights configurable per change trigger; geometric mean is unforgiving of a single collapsed dimension — a security collapse cannot be averaged away by continuity elsewhere).

`inherited_reputation(capability) = historical_reputation(capability) × inheritance_factor × behavior_continuity_confidence`, floored by policy (`min_inherited_score`), and the passport records the full computation for explainability. Policy can require `REVERIFY` (fresh human or platform verification gate) when the factor drops below a configured threshold or the change is in a sensitive class (owner transfer, capability escalation to high-risk).

## Reasoning
Geometric mean + per-trigger weights gives policy owners tunable, explainable behavior; storing the assessment makes every trust reduction auditable (spec §23, §75-demo).
