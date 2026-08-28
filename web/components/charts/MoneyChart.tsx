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
import { armColor } from "@/components/ui";
import { useStaticRender } from "@/lib/motion";
import {
  axisLabelStyle,
  axisLineStyle,
  axisTick,
  gridStyle,
  legendFormatter,
  legendWrapperStyle,
  tooltipContentStyle,
  tooltipLabelStyle,
} from "@/components/charts/chartTheme";
import { ARM_LABEL } from "@/components/ui";

const ARMS = ["dobara", "razorpay_default", "aggressive_8x", "oracle", "do_nothing"] as const;

// Colour is never the sole carrier of meaning (docs/10-REDESIGN.md §6) -- each arm also
// gets its own dash pattern, so the lines are distinguishable in grayscale/colourblind
// simulation and on a printed page.
const ARM_DASH: Record<(typeof ARMS)[number], string | undefined> = {
  dobara: undefined,
  razorpay_default: "6 3",
  aggressive_8x: "2 3",
  oracle: "1 4",
  do_nothing: "8 4 2 4",
};

export function MoneyChart({ data }: { data: MoneyChartData }) {
  const [metric, setMetric] = useState<"net" | "gross">("net");
  const isStatic = useStaticRender();

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
        <div className="font-mono text-xs text-text-muted">
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
          <CartesianGrid stroke={gridStyle.stroke} vertical={false} />
          <Legend
            verticalAlign="top"
            align="center"
            wrapperStyle={legendWrapperStyle}
            formatter={legendFormatter}
          />
          <XAxis
            dataKey="cycle"
            stroke={axisLineStyle.stroke}
            tick={axisTick()}
            label={{ value: "Cycle", position: "insideBottom", offset: -14, ...axisLabelStyle() }}
          />
          <YAxis
            stroke={axisLineStyle.stroke}
            tick={axisTick()}
            tickFormatter={(v: number) => formatInr(v, { compact: true })}
            width={70}
          />
          <Tooltip
            contentStyle={tooltipContentStyle}
            labelStyle={tooltipLabelStyle}
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
              strokeDasharray={ARM_DASH[arm]}
              dot={false}
              isAnimationActive={!isStatic}
              name={arm}
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
