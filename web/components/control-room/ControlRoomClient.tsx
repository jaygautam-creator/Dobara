"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import type { AskWhyEntry, CounterOut, DecisionOut, QueueRow } from "@/lib/types";
import { formatInr, formatNumber } from "@/lib/format";
import { Badge, Card, StatTile } from "@/components/ui";
import { DecisionCard } from "@/components/DecisionCard";

const ACTION_BADGE_COLOR: Record<string, "good" | "warning" | "critical" | "neutral"> = {
  schedule_debit: "good",
  offer_date_change: "neutral",
  stop: "neutral",
  abstain: "warning",
  escalate_to_human: "critical",
};

const RESTRAINED_ACTIONS = new Set(["stop", "abstain", "escalate_to_human"]);

const REVEAL_INTERVAL_MS = 45;

export function ControlRoomClient({
  rows,
  counters,
  topCaseDecision,
  topCaseAskWhy,
  approvals,
}: {
  rows: QueueRow[];
  counters: CounterOut;
  topCaseDecision: DecisionOut;
  topCaseAskWhy: AskWhyEntry | null;
  approvals: DecisionOut[];
}) {
  const [revealed, setRevealed] = useState(0);
  const [comparing, setComparing] = useState(false);
  const [selectedId, setSelectedId] = useState<number>(topCaseDecision.mandate_id);
  const [restrainedOnly, setRestrainedOnly] = useState(false);

  const restrainedCount = useMemo(
    () => rows.filter((r) => RESTRAINED_ACTIONS.has(r.terminal_action_type)).length,
    [rows],
  );

  useEffect(() => {
    if (revealed >= rows.length) return;
    const t = setTimeout(() => setRevealed((n) => n + 1), REVEAL_INTERVAL_MS);
    return () => clearTimeout(t);
  }, [revealed, rows.length]);

  const visibleRows = rows
    .slice(0, revealed)
    .filter((r) => !restrainedOnly || RESTRAINED_ACTIONS.has(r.terminal_action_type));
  const streaming = revealed < rows.length;
  const progress = revealed / Math.max(rows.length, 1);

  const selectedRow = useMemo(
    () => rows.find((r) => r.mandate_id === selectedId) ?? rows[0],
    [rows, selectedId],
  );
  const activeDecision = selectedId === topCaseDecision.mandate_id ? topCaseDecision : null;

  return (
    <div className="space-y-8">
      <div>
        <div className="mb-3 flex items-center justify-between">
          <div className="text-xs text-text-muted">
            {streaming
              ? `Streaming batch — ${revealed}/${rows.length} cases`
              : `Batch complete — ${rows.length} cases`}
          </div>
          <button
            onClick={() => setComparing((c) => !c)}
            className={`rounded-md border px-3 py-1.5 text-xs font-semibold transition-colors ${
              comparing
                ? "border-arm-aggressive-8x bg-arm-aggressive-8x/15 text-arm-aggressive-8x"
                : "border-border bg-surface-1 text-text-secondary hover:bg-surface-2"
            }`}
          >
            {comparing ? "Showing: aggressive_8x would have..." : "Show what aggressive_8x would have done"}
          </button>
        </div>
        <div className="h-1 w-full overflow-hidden rounded-full bg-surface-2">
          <div
            className="h-full bg-arm-dobara transition-all"
            style={{ width: `${progress * 100}%` }}
          />
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
        <StatTile
          label="₹ at risk (this cycle)"
          value={formatInr(counters.amount_at_risk_inr, { compact: true })}
          source="sum of each mandate's due amount for its current billing cycle only"
        />
        <StatTile
          label="₹ recovered (gross, all cycles)"
          value={formatInr(
            comparing ? counters.comparison_aggressive_8x_gross_recovered_inr : counters.gross_recovered_inr,
            { compact: true },
          )}
          source="cumulative across every cycle simulated per mandate -- not comparable to at-risk"
        />
        <StatTile
          label="₹ net LTV"
          tone="good"
          value={formatInr(
            comparing ? counters.comparison_aggressive_8x_net_ltv_inr : counters.net_ltv_inr,
            { compact: true },
          )}
        />
        <StatTile label="Notifications sent" value={formatNumber(counters.notifications_sent)} />
        <StatTile
          label="Revocations"
          tone={comparing ? "critical" : "good"}
          value={formatNumber(comparing ? counters.comparison_aggressive_8x_revocations : counters.revocations)}
        />
        <StatTile
          label="Attempts not made"
          tone="good"
          value={formatNumber(counters.attempts_not_made)}
          source="the whole thesis in one tile"
        />
      </div>

      {approvals.length > 0 && (
        <Card>
          <h3 className="mb-2 text-sm font-semibold text-text-primary">
            Approval queue ({approvals.length})
          </h3>
          <p className="text-xs text-text-secondary">
            Decisions above the human sign-off threshold — nothing above it runs
            autonomously.
          </p>
        </Card>
      )}

      <div className="grid gap-6 lg:grid-cols-[1fr_1.1fr]">
        <div>
          <div className="mb-3 flex items-center justify-between">
            <h3 className="text-sm font-semibold text-text-primary">
              Case queue, ranked by ₹ at risk
            </h3>
            <div className="flex items-center rounded-md border border-border bg-surface-1 p-0.5 text-xs">
              <button
                onClick={() => setRestrainedOnly(false)}
                className={`rounded px-2 py-1 font-medium transition-colors ${
                  !restrainedOnly
                    ? "bg-surface-2 text-text-primary"
                    : "text-text-secondary hover:text-text-primary"
                }`}
              >
                All {rows.length}
              </button>
              <button
                onClick={() => setRestrainedOnly(true)}
                className={`rounded px-2 py-1 font-medium transition-colors ${
                  restrainedOnly
                    ? "bg-arm-dobara/15 text-arm-dobara"
                    : "text-text-secondary hover:text-text-primary"
                }`}
              >
                Ended in stop or abstain ({restrainedCount})
              </button>
            </div>
          </div>
          <div className="max-h-[720px] overflow-y-auto rounded-lg border border-border">
            <table className="w-full border-collapse text-sm">
              <tbody>
                {visibleRows.map((row) => (
                  <tr
                    key={row.mandate_id}
                    onClick={() => setSelectedId(row.mandate_id)}
                    className={`cursor-pointer border-b border-border last:border-0 transition-colors hover:bg-surface-2 ${
                      selectedRow?.mandate_id === row.mandate_id ? "bg-arm-dobara/[0.08]" : "bg-surface-1"
                    }`}
                  >
                    <td className="px-3 py-2">
                      <div className="font-medium text-text-primary">#{row.mandate_id}</div>
                      <div className="text-[11px] text-text-muted">
                        {row.bank_id} · {row.merchant_category}
                      </div>
                    </td>
                    <td className="px-3 py-2">
                      <Badge color={ACTION_BADGE_COLOR[row.action_type] ?? "neutral"}>
                        {row.action_type}
                      </Badge>
                      {row.terminal_action_type !== row.action_type &&
                        RESTRAINED_ACTIONS.has(row.terminal_action_type) && (
                          <span className="ml-1.5 inline-block">
                            <Badge color={ACTION_BADGE_COLOR[row.terminal_action_type] ?? "neutral"}>
                              → {row.terminal_action_type}
                            </Badge>
                          </span>
                        )}
                      {row.regime_shift_bank && (
                        <span className="ml-1.5 text-[10px] text-status-warning">shift</span>
                      )}
                    </td>
                    <td className="tabular-nums px-3 py-2 text-right font-medium text-text-primary">
                      {formatInr(row.amount)}
                    </td>
                    <td className="px-3 py-2 text-right">
                      <Link
                        href={`/audit/${row.mandate_id}`}
                        onClick={(e) => e.stopPropagation()}
                        className="text-[11px] text-arm-dobara hover:underline"
                      >
                        full audit →
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        <div className="lg:sticky lg:top-20 lg:self-start">
          <h3 className="mb-3 text-sm font-semibold text-text-primary">Active case</h3>
          {activeDecision ? (
            <DecisionCard decision={activeDecision} askWhy={topCaseAskWhy} />
          ) : (
            <Card>
              <p className="text-sm text-text-secondary">
                Full decision detail for mandate #{selectedId} is on its own page (kept out
                of the Control Room bundle — see <code>/audit/{selectedId}</code>).
              </p>
              <Link
                href={`/audit/${selectedId}`}
                className="mt-3 inline-block text-sm font-medium text-arm-dobara hover:underline"
              >
                Open full audit →
              </Link>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}
