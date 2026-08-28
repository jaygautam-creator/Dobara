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
import { useStaticRender } from "@/lib/motion";
import {
  axisLineStyle,
  axisTick,
  gridStyle,
  legendFormatter,
  legendWrapperStyle,
  tooltipContentStyle,
} from "@/components/charts/chartTheme";

export function SensitivityChart({
  points,
  calibratedValue,
  breakEvenValue,
}: {
  points: SensitivityPoint[];
  calibratedValue: number;
  breakEvenValue?: number;
}) {
  const isStatic = useStaticRender();
  const rows = points.map((p) => ({
    hazard: p.hazard_per_failure_notification,
    dobara: p.dobara_mean_net_ltv,
    razorpay_default: p.razorpay_default_mean_net_ltv,
    aggressive_8x: p.aggressive_8x_mean_net_ltv,
  }));

  return (
    <ResponsiveContainer width="100%" height={340}>
      <LineChart data={rows} margin={{ top: 8, right: 24, bottom: 24, left: 8 }}>
        <CartesianGrid stroke={gridStyle.stroke} vertical={false} />
        <Legend
          verticalAlign="top"
          align="center"
          wrapperStyle={legendWrapperStyle}
          formatter={legendFormatter}
        />
        <XAxis
          dataKey="hazard"
          stroke={axisLineStyle.stroke}
          tick={axisTick()}
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
          stroke={axisLineStyle.stroke}
          tick={axisTick()}
          tickFormatter={(v: number) => formatInr(v, { compact: true })}
          width={64}
        />
        <Tooltip
          contentStyle={tooltipContentStyle}
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
        {(["dobara", "razorpay_default", "aggressive_8x"] as const).map((arm, i) => (
          <Line
            key={arm}
            type="monotone"
            dataKey={arm}
            stroke={armColor(arm)}
            strokeWidth={arm === "dobara" ? 3 : 2}
            strokeDasharray={i === 0 ? undefined : i === 1 ? "6 3" : "2 3"}
            dot={{ r: 3 }}
            isAnimationActive={!isStatic}
            name={arm}
          />
        ))}
      </LineChart>
    </ResponsiveContainer>
  );
}
