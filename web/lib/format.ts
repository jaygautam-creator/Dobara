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

export function formatCiInr(point: number, lo: number, hi: number, compact = true): string {
  return `${formatInr(point, { compact })} [${formatInr(lo, { compact })}, ${formatInr(hi, { compact })}]`;
}

export function formatPct(value: number, digits = 1): string {
  return `${(value * 100).toFixed(digits)}%`;
}

export function formatCiPct(point: number, lo: number, hi: number, digits = 1): string {
  return `${formatPct(point, digits)} [${formatPct(lo, digits)}, ${formatPct(hi, digits)}]`;
}

export function formatCiCount(point: number, lo: number, hi: number): string {
  return `${formatNumber(point)} [${formatNumber(lo)}, ${formatNumber(hi)}]`;
}

export function formatNumber(value: number, digits = 0): string {
  return value.toLocaleString("en-IN", { maximumFractionDigits: digits, minimumFractionDigits: digits });
}
