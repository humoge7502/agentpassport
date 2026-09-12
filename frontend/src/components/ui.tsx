/** Core UI primitives — AgentPassport design system (ADR-009). */

import type { ReactNode } from "react";
import { humanize, pct, type DecisionTone } from "../lib/format";

export function Card({
  children,
  className = "",
  as: Tag = "section",
}: {
  children: ReactNode;
  className?: string;
  as?: "section" | "div" | "article";
}) {
  return (
    <Tag
      className={`rounded-(--radius-md) border border-(--color-line-soft) bg-(--color-surface) ${className}`}
    >
      {children}
    </Tag>
  );
}

export function CardHeader({
  title,
  subtitle,
  action,
}: {
  title: string;
  subtitle?: string;
  action?: ReactNode;
}) {
  return (
    <div className="flex items-start justify-between gap-4 border-b border-(--color-line-soft) px-4 py-3">
      <div>
        <h2 className="text-[13px] font-semibold tracking-wide text-(--color-ink)">
          {title}
        </h2>
        {subtitle && (
          <p className="mt-0.5 text-xs text-(--color-ink-faint)">{subtitle}</p>
        )}
      </div>
      {action}
    </div>
  );
}

const toneClass: Record<DecisionTone, string> = {
  allow: "text-(--color-allow) border-(--color-allow)/30 bg-(--color-allow)/10",
  condition: "text-(--color-condition) border-(--color-condition)/30 bg-(--color-condition)/10",
  deny: "text-(--color-deny) border-(--color-deny)/30 bg-(--color-deny)/10",
  unknown: "text-(--color-unknown) border-(--color-unknown)/30 bg-(--color-unknown)/10",
};

export function Badge({
  children,
  tone = "unknown",
  mono = false,
}: {
  children: ReactNode;
  tone?: DecisionTone;
  mono?: boolean;
}) {
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-(--radius-sm) border px-1.5 py-0.5 text-[11px] font-medium ${toneClass[tone]} ${mono ? "mono" : ""}`}
    >
      {children}
    </span>
  );
}

export function DecisionBadge({ decision }: { decision: string }) {
  const tone: DecisionTone = decision === "ALLOW" ? "allow"
    : decision === "DENY" ? "deny"
    : decision === "UNKNOWN" ? "unknown"
    : "condition";
  const label = decision === "HUMAN_APPROVAL" ? "HUMAN APPROVAL" : decision;
  return <Badge tone={tone}>{label}</Badge>;
}

/** Score + uncertainty always co-displayed (spec §21). */
export function ScoreChip({
  score: s,
  confidence,
  size = "md",
}: {
  score: number | null;
  confidence: number | null;
  size?: "sm" | "md" | "lg";
}) {
  const unknown = s === null || s === undefined;
  const level = unknown
    ? "var(--color-unknown)"
    : s >= 85 ? "var(--color-trust-5)"
    : s >= 75 ? "var(--color-trust-4)"
    : s >= 60 ? "var(--color-trust-3)"
    : s >= 40 ? "var(--color-trust-2)"
    : "var(--color-trust-1)";
  const text = unknown ? "UNKNOWN" : s.toFixed(1);
  const sizes = {
    sm: "text-base",
    md: "text-xl",
    lg: "text-3xl",
  } as const;
  return (
    <span className="inline-flex items-baseline gap-2" title={`score ${text}, confidence ${pct(confidence ?? 0, 1)}`}>
      <span className={`num mono font-semibold ${sizes[size]}`} style={{ color: level }}>
        {text}
      </span>
      <span className="text-[11px] text-(--color-ink-faint)">
        {unknown ? "insufficient evidence" : `± ${pct(confidence, 1)} conf.`}
      </span>
    </span>
  );
}

export function ConfidenceBar({ confidence }: { confidence: number }) {
  return (
    <div
      className="h-1.5 w-full overflow-hidden rounded-full bg-(--color-surface-3)"
      role="meter"
      aria-valuenow={Math.round(confidence * 100)}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-label={`confidence ${pct(confidence)}`}
    >
      <div
        className="h-full rounded-full bg-(--color-accent) transition-[width] duration-200 ease-out"
        style={{ width: `${Math.min(100, confidence * 100)}%` }}
      />
    </div>
  );
}

export function StatCard({
  label,
  value,
  hint,
  tone,
}: {
  label: string;
  value: ReactNode;
  hint?: string;
  tone?: DecisionTone;
}) {
  const color = tone === "allow" ? "text-(--color-allow)"
    : tone === "deny" ? "text-(--color-deny)"
    : tone === "condition" ? "text-(--color-condition)"
    : "text-(--color-ink)";
  return (
    <Card as="div" className="px-4 py-3">
      <p className="text-[11px] font-medium tracking-wide text-(--color-ink-faint) uppercase">
        {label}
      </p>
      <p className={`num mono mt-1 text-2xl font-semibold ${color}`}>{value}</p>
      {hint && <p className="mt-0.5 text-xs text-(--color-ink-faint)">{hint}</p>}
    </Card>
  );
}

export function Skeleton({ className = "" }: { className?: string }) {
  return (
    <div
      className={`pulse-soft rounded-(--radius-sm) bg-(--color-surface-3) ${className}`}
      aria-hidden
    />
  );
}

export function EmptyState({
  title,
  hint,
  action,
}: {
  title: string;
  hint?: string;
  action?: ReactNode;
}) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 px-6 py-14 text-center">
      <div
        className="mb-1 h-10 w-10 rounded-(--radius-md) border border-(--color-line) bg-(--color-surface-2)"
        aria-hidden
      />
      <p className="text-sm font-medium text-(--color-ink-dim)">{title}</p>
      {hint && <p className="max-w-sm text-xs text-(--color-ink-faint)">{hint}</p>}
      {action}
    </div>
  );
}

export function ErrorState({ message }: { message: string }) {
  return (
    <div
      role="alert"
      className="flex flex-col items-center gap-2 rounded-(--radius-md) border border-(--color-deny)/30 bg-(--color-deny)/5 px-6 py-10 text-center"
    >
      <p className="text-sm font-medium text-(--color-deny)">Something failed</p>
      <p className="max-w-md font-mono text-xs text-(--color-ink-dim)">{message}</p>
    </div>
  );
}

export function Table({
  headers,
  children,
  caption,
}: {
  headers: string[];
  children: ReactNode;
  caption?: string;
}) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full border-collapse text-left text-[13px]">
        {caption && <caption className="sr-only">{caption}</caption>}
        <thead>
          <tr className="border-b border-(--color-line-soft)">
            {headers.map((h) => (
              <th
                key={h}
                scope="col"
                className="px-4 py-2 text-[11px] font-medium tracking-wide text-(--color-ink-faint) uppercase"
              >
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-(--color-line-soft)">{children}</tbody>
      </table>
    </div>
  );
}

export function Td({
  children,
  mono = false,
  className = "",
}: {
  children: ReactNode;
  mono?: boolean;
  className?: string;
}) {
  return (
    <td className={`px-4 py-2 align-middle text-(--color-ink-dim) ${mono ? "mono" : ""} ${className}`}>
      {children}
    </td>
  );
}

export function Button({
  children,
  onClick,
  variant = "default",
  disabled = false,
  type = "button",
  ariaLabel,
}: {
  children: ReactNode;
  onClick?: () => void;
  variant?: "default" | "primary" | "danger";
  disabled?: boolean;
  type?: "button" | "submit";
  ariaLabel?: string;
}) {
  const base =
    "inline-flex items-center gap-1.5 rounded-(--radius-sm) border px-2.5 py-1.5 text-xs font-medium transition-colors duration-150 ease-out disabled:cursor-not-allowed disabled:opacity-50";
  const variants = {
    default:
      "border-(--color-line) bg-(--color-surface-2) text-(--color-ink-dim) hover:bg-(--color-surface-3) hover:text-(--color-ink)",
    primary:
      "border-(--color-accent-dim) bg-(--color-accent-dim)/40 text-(--color-accent) hover:bg-(--color-accent-dim)/70",
    danger:
      "border-(--color-deny)/30 bg-(--color-deny)/10 text-(--color-deny) hover:bg-(--color-deny)/20",
  } as const;
  return (
    <button
      type={type}
      aria-label={ariaLabel}
      disabled={disabled}
      onClick={onClick}
      className={`${base} ${variants[variant]}`}
    >
      {children}
    </button>
  );
}

export function KeyValue({ k, v, mono = true }: { k: string; v: ReactNode; mono?: boolean }) {
  return (
    <div className="flex items-baseline justify-between gap-4 py-1.5">
      <dt className="text-xs text-(--color-ink-faint)">{humanize(k)}</dt>
      <dd className={`text-right text-[13px] text-(--color-ink) ${mono ? "mono" : ""}`}>
        {v}
      </dd>
    </div>
  );
}
