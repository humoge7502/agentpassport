/** Shared formatting + semantic color mapping (ADR-009 trust semantics). */

export function shortId(id: string | null | undefined, n = 8): string {
  if (!id) return "—";
  return id.length <= n ? id : id.slice(0, n);
}

export function pct(v: number | null | undefined, digits = 0): string {
  if (v === null || v === undefined) return "—";
  return `${(v * 100).toFixed(digits)}%`;
}

export function score(v: number | null | undefined): string {
  if (v === null || v === undefined) return "UNKNOWN";
  return v.toFixed(1);
}

export function when(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  const diff = Date.now() - d.getTime();
  const mins = Math.round(diff / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.round(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.round(hours / 24);
  if (days < 30) return `${days}d ago`;
  return d.toISOString().slice(0, 10);
}

export type DecisionTone = "allow" | "condition" | "deny" | "unknown";

export function decisionTone(decision: string | null | undefined): DecisionTone {
  switch (decision) {
    case "ALLOW":
      return "allow";
    case "HUMAN_APPROVAL":
    case "REVERIFY":
      return "condition";
    case "DENY":
      return "deny";
    default:
      return "unknown";
  }
}

/** Trust ramp: score+confidence → 5-step level (compromised → verified). */
export function trustLevel(
  s: number | null | undefined,
  conf: number | null | undefined,
): 1 | 2 | 3 | 4 | 5 {
  if (s === null || s === undefined || conf === null || conf === undefined) return 1;
  if (s >= 85 && conf >= 0.6) return 5;
  if (s >= 75) return 4;
  if (s >= 60) return 3;
  if (s >= 40) return 2;
  return 1;
}

export function statusTone(status: string): "allow" | "condition" | "deny" | "unknown" {
  if (status === "active") return "allow";
  if (status === "suspended") return "condition";
  if (status === "revoked") return "deny";
  return "unknown";
}

export function severityTone(sev: string): DecisionTone {
  if (sev === "high" || sev === "critical") return "deny";
  if (sev === "medium") return "condition";
  return "unknown";
}

export function humanize(s: string): string {
  return s.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}
