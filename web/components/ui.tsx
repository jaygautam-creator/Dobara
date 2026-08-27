import type { ReactNode } from "react";

export function Card({
  children,
  className = "",
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <div
      className={`rounded-lg border border-border bg-surface-1 p-5 ${className}`}
    >
      {children}
    </div>
  );
}

export function SectionHeading({
  eyebrow,
  title,
  description,
}: {
  eyebrow?: string;
  title: string;
  description?: ReactNode;
}) {
  return (
    <div className="mb-6">
      {eyebrow && (
        <div className="mb-1 text-xs font-medium uppercase tracking-wider text-text-muted">
          {eyebrow}
        </div>
      )}
      <h2 className="text-xl font-semibold text-text-primary">{title}</h2>
      {description && (
        <p className="mt-1.5 max-w-3xl text-sm leading-relaxed text-text-secondary">
          {description}
        </p>
      )}
    </div>
  );
}

/** A single number, always with its 95% CI and never bare -- CLAUDE.md's "every number
 * reported must have a confidence interval and a stated source." */
export function StatTile({
  label,
  value,
  ciText,
  source,
  tone = "default",
}: {
  label: string;
  value: string;
  ciText?: string;
  source?: string;
  tone?: "default" | "good" | "warning" | "critical";
}) {
  const toneClass =
    tone === "good"
      ? "text-status-good"
      : tone === "warning"
        ? "text-status-warning"
        : tone === "critical"
          ? "text-status-critical"
          : "text-text-primary";
  return (
    <div className="rounded-lg border border-border bg-surface-1 p-4">
      <div className="text-xs font-medium uppercase tracking-wider text-text-muted">
        {label}
      </div>
      <div className={`mt-1.5 tabular-nums text-2xl font-semibold ${toneClass}`}>
        {value}
      </div>
      {ciText && (
        <div className="mt-1 tabular-nums text-xs text-text-secondary">95% CI {ciText}</div>
      )}
      {source && <div className="mt-1 text-[11px] text-text-muted">{source}</div>}
    </div>
  );
}

export function Badge({
  children,
  color = "neutral",
}: {
  children: ReactNode;
  color?: "neutral" | "good" | "warning" | "critical" | "arm";
}) {
  const classes =
    color === "good"
      ? "bg-status-good/15 text-status-good"
      : color === "warning"
        ? "bg-status-warning/20 text-status-warning"
        : color === "critical"
          ? "bg-status-critical/15 text-status-critical"
          : "bg-surface-2 text-text-secondary";
  return (
    <span
      className={`inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-medium ${classes}`}
    >
      {children}
    </span>
  );
}

const ARM_COLOR_VAR: Record<string, string> = {
  dobara: "var(--arm-dobara)",
  razorpay_default: "var(--arm-razorpay-default)",
  aggressive_8x: "var(--arm-aggressive-8x)",
  do_nothing: "var(--arm-do-nothing)",
  oracle: "var(--arm-oracle)",
};

export const ARM_LABEL: Record<string, string> = {
  dobara: "dobara",
  razorpay_default: "razorpay_default",
  aggressive_8x: "aggressive_8x",
  do_nothing: "do_nothing",
  oracle: "oracle (ceiling)",
};

export function ArmSwatch({ arm }: { arm: string }) {
  return (
    <span
      className="mr-1.5 inline-block h-2.5 w-2.5 rounded-full align-middle"
      style={{ background: ARM_COLOR_VAR[arm] ?? "var(--text-muted)" }}
    />
  );
}

export function armColor(arm: string): string {
  return ARM_COLOR_VAR[arm] ?? "var(--text-muted)";
}

export function Callout({
  tone = "default",
  title,
  children,
}: {
  tone?: "default" | "good" | "warning" | "critical";
  title?: string;
  children: ReactNode;
}) {
  const border =
    tone === "good"
      ? "border-status-good/40"
      : tone === "warning"
        ? "border-status-warning/40"
        : tone === "critical"
          ? "border-status-critical/40"
          : "border-border";
  return (
    <div className={`rounded-lg border ${border} bg-surface-1 p-4`}>
      {title && <div className="mb-1.5 text-sm font-semibold text-text-primary">{title}</div>}
      <div className="text-sm leading-relaxed text-text-secondary">{children}</div>
    </div>
  );
}
