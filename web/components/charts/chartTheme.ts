// Shared Recharts axis/legend/tooltip styling -- previously repeated near-verbatim
// across MoneyChart, SensitivityChart, and ReliabilityChart (docs/10-REDESIGN.md §4,
// "extract the repeated axis/legend/tooltip styling ... into a shared chartTheme.ts").
// Every number Recharts renders (axis ticks, tooltip values) goes through Geist Mono via
// `tickStyle`/`tooltipContentStyle`'s fontFamily -- docs/10-REDESIGN.md §2's "every
// number moves to Geist Mono" applies inside SVG text just as much as in a <table>.
import { ARM_LABEL } from "@/components/ui";

const NUMBER_FONT = "var(--font-geist-mono)";

export const gridStyle = { stroke: "var(--gridline)" } as const;

export const axisLineStyle = { stroke: "var(--baseline)" } as const;

export function axisTick(fontSize = 12) {
  return { fill: "var(--text-muted)", fontSize, fontFamily: NUMBER_FONT } as const;
}

export function axisLabelStyle(fontSize = 12) {
  return { fill: "var(--text-muted)", fontSize } as const;
}

export const legendWrapperStyle = {
  fontSize: 12,
  color: "var(--text-secondary)",
  paddingBottom: 12,
} as const;

export function legendFormatter(value: string): string {
  return ARM_LABEL[value] ?? value;
}

export const tooltipContentStyle = {
  background: "var(--surface-2)",
  border: "1px solid var(--border)",
  borderRadius: 8,
  fontSize: 12,
  fontFamily: NUMBER_FONT,
} as const;

export const tooltipLabelStyle = { color: "var(--text-primary)" } as const;
