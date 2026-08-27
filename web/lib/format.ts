// Every money/probability figure this UI renders should go through one of these --
// CLAUDE.md: "Every number reported must have a confidence interval and a stated
// source. No bare point estimates anywhere in README, UI, or video."

export function formatInr(value: number, opts: { compact?: boolean } = {}): string {
  if (opts.compact) {
    const abs = Math.abs(value);
    if (abs >= 1e7) return `₹${(value / 1e7).toFixed(2)}Cr`;
    if (abs >= 1e5) return `₹${(value / 1e5).toFixed(2)}L`;
    if (abs >= 1e3) return `₹${(value / 1e3).toFixed(1)}k`;
  }
  return `₹${value.toLocaleString("en-IN", { maximumFractionDigits: 0 })}`;
}

export function formatInrPrecise(value: number): string {
  return `₹${value.toLocaleString("en-IN", { maximumFractionDigits: 2 })}`;
}

/** Null-safe: a genuinely undefined CIValue (n_seeds: 0) renders as "n/a", never as 0. */
export function formatCiInr(
  point: number | null,
  lo: number | null,
  hi: number | null,
  compact = true,
): string {
  if (point === null || lo === null || hi === null) return "n/a — no attempts made";
  return `${formatInr(point, { compact })} [${formatInr(lo, { compact })}, ${formatInr(hi, { compact })}]`;
}

export function formatPct(value: number, digits = 1): string {
  return `${(value * 100).toFixed(digits)}%`;
}

export function formatCiPct(point: number, lo: number, hi: number, digits = 1): string {
  return `${formatPct(point, digits)} [${formatPct(lo, digits)}, ${formatPct(hi, digits)}]`;
}

/** Null-safe: a genuinely undefined CIValue (n_seeds: 0, e.g. an arm that made zero
 * attempts) renders as "n/a", never as 0 -- rendering 0 would claim a measured rate that
 * doesn't exist. */
export function formatCiPctOrNA(
  point: number | null,
  lo: number | null,
  hi: number | null,
  digits = 1,
): string {
  if (point === null || lo === null || hi === null) return "n/a — no attempts made";
  return formatCiPct(point, lo, hi, digits);
}

export function formatCiCount(point: number | null, lo: number | null, hi: number | null): string {
  if (point === null || lo === null || hi === null) return "n/a — no attempts made";
  return `${formatNumber(point)} [${formatNumber(lo)}, ${formatNumber(hi)}]`;
}

export function formatNumber(value: number, digits = 0): string {
  return value.toLocaleString("en-IN", { maximumFractionDigits: digits, minimumFractionDigits: digits });
}
