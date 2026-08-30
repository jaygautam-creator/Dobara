import type { ReactNode } from "react";

/** The four surface treatments, docs/10-REDESIGN.md §3.2. `raised` is the default card
 * look this project shipped with pre-redesign -- kept as the default variant so existing
 * `<Card>` call sites render unchanged until their route is deliberately redesigned.
 * `feature` is rationed: exactly one per page, the page's focal claim. */
export type SurfaceVariant = "plain" | "inset" | "raised" | "feature";

const SURFACE_CLASS: Record<SurfaceVariant, string> = {
  plain: "",
  inset: "rounded-md bg-surface-0 border border-border",
  raised: "rounded-lg border border-border bg-surface-1",
  feature:
    "rounded-lg border border-arm-dobara/40 bg-surface-1 shadow-[0_0_0_1px_rgba(42,120,214,0.04)_inset]",
};

export function Card({
  children,
  className = "",
  variant = "raised",
}: {
  children: ReactNode;
  className?: string;
  variant?: SurfaceVariant;
}) {
  const padded = variant === "plain" ? "" : "p-5";
  return <div className={`${SURFACE_CLASS[variant]} ${padded} ${className}`}>{children}</div>;
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

export type StatTileSize = "hero" | "default" | "compact";

const STAT_VALUE_SIZE: Record<StatTileSize, string> = {
  hero: "text-step-6",
  default: "text-2xl",
  compact: "text-step-2",
};

const STAT_PADDING: Record<StatTileSize, string> = {
  hero: "p-6",
  default: "p-4",
  compact: "p-3",
};

/** Either a 95% CI, or an explicit written reason there isn't one -- the type system's
 * enforcement of CLAUDE.md's "every number reported must have a confidence interval and
 * a stated source" (docs/10-REDESIGN.md §4 `/control-room`: Session B left this as a
 * docstring convention; a call site could silently omit `ciText` and no one would notice
 * a live fixture counter had quietly lost its CI). `noCi` must name the actual reason
 * (e.g. "live fixture counter, not a statistical estimate"), not restate that there is
 * no CI. */
type StatTileCI = { ciText: string; noCi?: undefined } | { ciText?: undefined; noCi: string };

/** A single number. `source` is mandatory -- CLAUDE.md's "every number reported must
 * have a confidence interval and a stated source" applies equally across every `size`; a
 * `hero` or `compact` tile is not exempt from carrying a source just because it's
 * visually smaller. */
export function StatTile({
  label,
  value,
  source,
  tone = "default",
  size = "default",
  ...ci
}: {
  label: string;
  value: string;
  source: string;
  tone?: "default" | "good" | "warning" | "critical";
  size?: StatTileSize;
} & StatTileCI) {
  const toneClass =
    tone === "good"
      ? "text-status-good-text"
      : tone === "warning"
        ? "text-status-warning-text"
        : tone === "critical"
          ? "text-status-critical-text"
          : "text-text-primary";
  return (
    <div className={`rounded-lg border border-border bg-surface-1 ${STAT_PADDING[size]}`}>
      <div className="text-xs font-medium uppercase tracking-wider text-text-muted">{label}</div>
      <div
        className={`mt-1.5 font-mono tabular-nums font-semibold ${STAT_VALUE_SIZE[size]} ${toneClass}`}
      >
        {value}
      </div>
      {ci.ciText && (
        <div className="mt-1 font-mono tabular-nums text-xs text-text-secondary">
          95% CI {ci.ciText}
        </div>
      )}
      {ci.noCi && (
        <div className="mt-1 text-xs italic text-text-muted">no CI — {ci.noCi}</div>
      )}
      <div className="mt-1 text-[11px] break-words text-text-muted">{source}</div>
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
      ? "bg-status-good/15 text-status-good-text"
      : color === "warning"
        ? "bg-status-warning/20 text-status-warning-text"
        : color === "critical"
          ? "bg-status-critical/15 text-status-critical-text"
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
  id,
}: {
  tone?: "default" | "good" | "warning" | "critical";
  title?: string;
  children: ReactNode;
  id?: string;
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
    <div id={id} className={`rounded-lg border ${border} bg-surface-1 p-4 scroll-mt-20`}>
      {title && <div className="mb-1.5 text-sm font-semibold text-text-primary">{title}</div>}
      <div className="text-sm leading-relaxed text-text-secondary">{children}</div>
    </div>
  );
}
