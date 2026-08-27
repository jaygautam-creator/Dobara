"use client";

import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { SensitivityPoint } from "@/lib/types";
import { formatInr } from "@/lib/format";
import { ARM_LABEL, armColor } from "@/components/ui";

export function SensitivityChart({
  points,
  calibratedValue,
  breakEvenValue,
}: {
  points: SensitivityPoint[];
  calibratedValue: number;
  breakEvenValue?: number;
}) {
  const rows = points.map((p) => ({
    hazard: p.hazard_per_failure_notification,
    dobara: p.dobara_mean_net_ltv,
    razorpay_default: p.razorpay_default_mean_net_ltv,
    aggressive_8x: p.aggressive_8x_mean_net_ltv,
  }));

  return (
    <ResponsiveContainer width="100%" height={340}>
      <LineChart data={rows} margin={{ top: 8, right: 24, bottom: 24, left: 8 }}>
        <CartesianGrid stroke="var(--gridline)" vertical={false} />
        <Legend
          verticalAlign="top"
          align="center"
          wrapperStyle={{ fontSize: 12, color: "var(--text-secondary)", paddingBottom: 12 }}
          formatter={(value: string) => ARM_LABEL[value] ?? value}
        />
        <XAxis
          dataKey="hazard"
          stroke="var(--baseline)"
          tick={{ fill: "var(--text-muted)", fontSize: 12 }}
          tickFormatter={(v: number) => v.toFixed(3)}
          label={{
            value: "revocation.hazard_per_failure_notification",
            position: "insideBottom",
            offset: -14,
            fill: "var(--text-muted)",
            fontSize: 11,
          }}
        />
        <YAxis
          stroke="var(--baseline)"
          tick={{ fill: "var(--text-muted)", fontSize: 12 }}
          tickFormatter={(v: number) => formatInr(v, { compact: true })}
          width={64}
        />
        <Tooltip
          contentStyle={{
            background: "var(--surface-2)",
            border: "1px solid var(--border)",
            borderRadius: 8,
            fontSize: 12,
          }}
          formatter={(value, name) => [formatInr(Number(value)), ARM_LABEL[String(name)] ?? String(name)]}
          labelFormatter={(l) => `hazard = ${Number(l).toFixed(3)}`}
        />
        <ReferenceLine
          x={calibratedValue}
          stroke="var(--text-muted)"
          strokeDasharray="4 4"
          label={{ value: "calibrated", position: "top", fill: "var(--text-muted)", fontSize: 11 }}
        />
        {breakEvenValue !== undefined && (
          <ReferenceLine
            x={breakEvenValue}
            stroke="var(--status-critical)"
            strokeDasharray="4 4"
            label={{ value: "break-even", position: "top", fill: "var(--status-critical)", fontSize: 11 }}
          />
        )}
        {(["dobara", "razorpay_default", "aggressive_8x"] as const).map((arm) => (
          <Line
            key={arm}
            type="monotone"
            dataKey={arm}
            stroke={armColor(arm)}
            strokeWidth={arm === "dobara" ? 3 : 2}
            dot={{ r: 3 }}
            isAnimationActive={false}
            name={arm}
          />
        ))}
      </LineChart>
    </ResponsiveContainer>
  );
}
