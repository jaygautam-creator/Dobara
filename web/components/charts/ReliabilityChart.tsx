"use client";

import {
  CartesianGrid,
  Line,
  ResponsiveContainer,
  Scatter,
  ComposedChart,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { ReliabilityDiagram } from "@/lib/types";
import { formatPct } from "@/lib/format";

/** A calibration reliability diagram: predicted probability (x) vs observed frequency
 * (y), against the perfect-calibration diagonal. dataviz: sequential/identity color, one
 * axis pair, direct labels over a legend for a single series. */
export function ReliabilityChart({ diagram }: { diagram: ReliabilityDiagram }) {
  const points = diagram.prob_pred.map((p, i) => ({
    prob_pred: p,
    prob_true: diagram.prob_true[i],
  }));
  const diagonal = [
    { prob_pred: 0, prob_true: 0 },
    { prob_pred: 1, prob_true: 1 },
  ];

  return (
    <ResponsiveContainer width="100%" height={220}>
      <ComposedChart margin={{ top: 8, right: 16, bottom: 8, left: 8 }}>
        <CartesianGrid stroke="var(--gridline)" />
        <XAxis
          type="number"
          dataKey="prob_pred"
          domain={[0, 1]}
          stroke="var(--baseline)"
          tick={{ fill: "var(--text-muted)", fontSize: 11 }}
          tickFormatter={(v: number) => formatPct(v, 0)}
          label={{
            value: "Predicted probability",
            position: "insideBottom",
            offset: -4,
            fill: "var(--text-muted)",
            fontSize: 11,
          }}
        />
        <YAxis
          type="number"
          dataKey="prob_true"
          domain={[0, 1]}
          stroke="var(--baseline)"
          tick={{ fill: "var(--text-muted)", fontSize: 11 }}
          tickFormatter={(v: number) => formatPct(v, 0)}
          width={44}
        />
        <Tooltip
          contentStyle={{
            background: "var(--surface-2)",
            border: "1px solid var(--border)",
            borderRadius: 8,
            fontSize: 12,
          }}
          formatter={(value) => formatPct(Number(value), 1)}
        />
        <Line
          data={diagonal}
          dataKey="prob_true"
          stroke="var(--baseline)"
          strokeDasharray="4 4"
          dot={false}
          activeDot={false}
          legendType="none"
          isAnimationActive={false}
          name="perfect calibration"
        />
        <Scatter
          data={points}
          fill="var(--arm-dobara)"
          line={{ stroke: "var(--arm-dobara)", strokeWidth: 2 }}
          isAnimationActive={false}
        />
      </ComposedChart>
    </ResponsiveContainer>
  );
}
