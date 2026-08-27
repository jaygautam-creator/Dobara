"use client";

import { useState } from "react";
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { MoneyChartData } from "@/lib/types";
import { formatInr } from "@/lib/format";
import { ARM_LABEL, armColor } from "@/components/ui";

const ARMS = ["dobara", "razorpay_default", "aggressive_8x", "oracle", "do_nothing"] as const;

export function MoneyChart({ data }: { data: MoneyChartData }) {
  const [metric, setMetric] = useState<"net" | "gross">("net");

  const rows = data.cycle_index.map((cycle, i) => {
    const row: Record<string, number> = { cycle };
    for (const arm of ARMS) {
      row[arm] = data[arm][metric][i];
    }
    return row;
  });

  return (
    <div className="viz-root">
      <div className="mb-3 flex items-center justify-between">
        <div className="text-xs text-text-muted">
          Single seed {data.seed}, n={data.n_customers.toLocaleString("en-IN")} mandates —
          held out from both training and the 30-seed harness
        </div>
        <div className="flex overflow-hidden rounded-md border border-border text-xs">
          <button
            onClick={() => setMetric("net")}
            className={`px-3 py-1.5 font-medium transition-colors ${
              metric === "net"
                ? "bg-arm-dobara text-white"
                : "bg-surface-1 text-text-secondary hover:bg-surface-2"
            }`}
          >
            Net LTV
          </button>
          <button
            onClick={() => setMetric("gross")}
            className={`px-3 py-1.5 font-medium transition-colors ${
              metric === "gross"
                ? "bg-arm-dobara text-white"
                : "bg-surface-1 text-text-secondary hover:bg-surface-2"
            }`}
          >
            Gross recovered
          </button>
        </div>
      </div>
      <ResponsiveContainer width="100%" height={380}>
        <LineChart data={rows} margin={{ top: 8, right: 24, bottom: 24, left: 8 }}>
          <CartesianGrid stroke="var(--gridline)" vertical={false} />
          <Legend
            verticalAlign="top"
            align="center"
            wrapperStyle={{ fontSize: 12, color: "var(--text-secondary)", paddingBottom: 12 }}
            formatter={(value: string) => ARM_LABEL[value] ?? value}
          />
          <XAxis
            dataKey="cycle"
            stroke="var(--baseline)"
            tick={{ fill: "var(--text-muted)", fontSize: 12 }}
            label={{ value: "Cycle", position: "insideBottom", offset: -14, fill: "var(--text-muted)", fontSize: 12 }}
          />
          <YAxis
            stroke="var(--baseline)"
            tick={{ fill: "var(--text-muted)", fontSize: 12 }}
            tickFormatter={(v: number) => formatInr(v, { compact: true })}
            width={70}
          />
          <Tooltip
            contentStyle={{
              background: "var(--surface-2)",
              border: "1px solid var(--border)",
              borderRadius: 8,
              fontSize: 12,
            }}
            labelStyle={{ color: "var(--text-primary)" }}
            formatter={(value, name) => [
              formatInr(Number(value), { compact: true }),
              ARM_LABEL[String(name)] ?? String(name),
            ]}
            labelFormatter={(l) => `Cycle ${l}`}
          />
          {ARMS.map((arm) => (
            <Line
              key={arm}
              type="monotone"
              dataKey={arm}
              stroke={armColor(arm)}
              strokeWidth={arm === "dobara" ? 3 : 2}
              dot={false}
              isAnimationActive={false}
              name={arm}
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
