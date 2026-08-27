import type { ArmName, SummaryJson } from "@/lib/types";
import { formatCiCount, formatCiInr, formatNumber } from "@/lib/format";
import { ArmSwatch } from "@/components/ui";

const ARMS_IN_ORDER: ArmName[] = ["do_nothing", "razorpay_default", "aggressive_8x", "dobara", "oracle"];

export function ArmComparisonTable({ summary }: { summary: SummaryJson }) {
  return (
    <div className="overflow-x-auto rounded-lg border border-border">
      <table className="w-full min-w-[860px] border-collapse text-sm">
        <thead>
          <tr className="border-b border-border bg-surface-2 text-left text-xs uppercase tracking-wide text-text-muted">
            <th className="px-4 py-3 font-medium">Arm</th>
            <th className="px-4 py-3 text-right font-medium">Gross recovered</th>
            <th className="px-4 py-3 text-right font-medium">Net LTV (total)</th>
            <th className="px-4 py-3 text-right font-medium">Attempts (mean)</th>
            <th className="px-4 py-3 text-right font-medium">Notifications</th>
            <th className="px-4 py-3 text-right font-medium">Revocations</th>
          </tr>
        </thead>
        <tbody>
          {ARMS_IN_ORDER.map((arm) => {
            const m = summary.arms[arm];
            const isDobara = arm === "dobara";
            return (
              <tr
                key={arm}
                className={`border-b border-border last:border-0 ${
                  isDobara ? "bg-arm-dobara/[0.06]" : ""
                }`}
              >
                <td className="px-4 py-3 font-medium text-text-primary">
                  <ArmSwatch arm={arm} />
                  {arm}
                  {isDobara && (
                    <span className="ml-2 rounded-full bg-arm-dobara/15 px-2 py-0.5 text-[10px] font-semibold text-arm-dobara">
                      headline
                    </span>
                  )}
                </td>
                <td className="tabular-nums px-4 py-3 text-right text-text-secondary">
                  {arm === "do_nothing"
                    ? "₹0"
                    : formatCiInr(
                        m.gross_recovered_inr.point,
                        m.gross_recovered_inr.ci_lo,
                        m.gross_recovered_inr.ci_hi,
                      )}
                </td>
                <td
                  className={`tabular-nums px-4 py-3 text-right font-semibold ${
                    isDobara ? "text-arm-dobara" : "text-text-primary"
                  }`}
                >
                  {arm === "do_nothing"
                    ? "₹0"
                    : formatCiInr(m.net_ltv_total.point, m.net_ltv_total.ci_lo, m.net_ltv_total.ci_hi)}
                </td>
                <td className="tabular-nums px-4 py-3 text-right text-text-secondary">
                  {formatNumber(m.attempts_mean.point, 2)}
                </td>
                <td className="tabular-nums px-4 py-3 text-right text-text-secondary">
                  {arm === "do_nothing"
                    ? "0"
                    : formatCiCount(
                        m.notifications_total.point,
                        m.notifications_total.ci_lo,
                        m.notifications_total.ci_hi,
                      )}
                </td>
                <td
                  className={`tabular-nums px-4 py-3 text-right ${
                    isDobara ? "font-semibold text-status-good" : "text-text-secondary"
                  }`}
                >
                  {arm === "do_nothing"
                    ? "0"
                    : formatCiCount(
                        m.revocations_total.point,
                        m.revocations_total.ci_lo,
                        m.revocations_total.ci_hi,
                      )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
      <p className="border-t border-border bg-surface-2 px-4 py-2 text-[11px] text-text-muted">
        All values ± 95% bootstrap CI over {summary.n_seeds} seeds of{" "}
        {formatNumber(summary.n_customers_per_seed)} mandates each. Paired comparisons on
        identical seeds. Source: <code>artifacts/summary.json</code>.
      </p>
    </div>
  );
}
