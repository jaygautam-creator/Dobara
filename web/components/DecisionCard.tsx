import type { DecisionOut } from "@/lib/types";
import { formatInr, formatInrPrecise, formatPct } from "@/lib/format";
import { Badge, Card } from "@/components/ui";

const ACTION_LABEL: Record<string, string> = {
  schedule_debit: "Schedule debit",
  offer_date_change: "Offer date change",
  stop: "Stop",
  abstain: "Abstain",
  escalate_to_human: "Escalate to human",
};

export function AbstentionBanner({ decision }: { decision: DecisionOut }) {
  if (decision.chosen.action_type !== "abstain") return null;
  return (
    <div className="rounded-lg border border-status-warning/40 bg-status-warning/10 px-4 py-3 text-sm text-text-primary">
      <span className="font-semibold text-status-warning">Abstained.</span> Reason:{" "}
      <code className="text-text-secondary">{decision.chosen.abstain_reason}</code> — the
      agent declined to trust its own model here rather than guess.
    </div>
  );
}

export function DecisionCard({ decision, bankId, method, amount }: {
  decision: DecisionOut;
  bankId?: string;
  method?: string;
  amount?: number;
}) {
  const rm = decision.rupee_math;
  return (
    <Card className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <div className="text-xs uppercase tracking-wide text-text-muted">
            Mandate #{decision.mandate_id} · cycle {decision.cycle_index} · attempt{" "}
            {decision.attempt_index}
          </div>
          <div className="mt-0.5 text-lg font-semibold text-text-primary">
            {ACTION_LABEL[decision.chosen.action_type] ?? decision.chosen.action_type}
          </div>
        </div>
        <div className="flex items-center gap-2">
          {decision.requires_signoff && <Badge color="warning">needs sign-off</Badge>}
          <Badge>{bankId ?? decision.bank_id}</Badge>
          <Badge>{method ?? decision.method}</Badge>
        </div>
      </div>

      <AbstentionBanner decision={decision} />

      {/* SAW / rupee arithmetic term by term */}
      <div>
        <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-text-muted">
          Rupee math
        </h4>
        <div className="grid grid-cols-2 gap-x-6 gap-y-1.5 rounded-md bg-surface-0 p-3 text-sm sm:grid-cols-3">
          <Term label="P(success)" value={formatPct(rm.p_success, 1)} />
          <Term label="Amount" value={formatInrPrecise(amount ?? rm.amount)} />
          <Term label="P(revoke)" value={formatPct(rm.p_revoke, 2)} />
          <Term label="LTV remaining" value={formatInr(rm.ltv_remaining)} />
          <Term label="Cost" value={formatInr(rm.cost)} />
          <Term
            label="E[net]"
            value={formatInr(rm.expected_net)}
            emphasize={rm.expected_net >= 0 ? "good" : "critical"}
          />
        </div>
        <div className="mt-1.5 text-[11px] text-text-muted">
          95% confidence band on E[net]: [{formatInr(decision.confidence_band[0])},{" "}
          {formatInr(decision.confidence_band[1])}]
        </div>
      </div>

      {/* rejected alternatives */}
      {decision.rejected_alternatives.length > 0 && (
        <div>
          <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-text-muted">
            Rejected alternatives ({decision.rejected_alternatives.length})
          </h4>
          <ul className="max-h-40 space-y-1 overflow-y-auto rounded-md bg-surface-0 p-3 text-xs">
            {decision.rejected_alternatives.slice(0, 12).map((alt, i) => (
              <li key={i} className="flex items-center justify-between gap-3 text-text-secondary">
                <span className="truncate">{alt.description}</span>
                <span className="tabular-nums shrink-0">{formatInr(alt.expected_net)}</span>
              </li>
            ))}
            {decision.rejected_alternatives.length > 12 && (
              <li className="text-text-muted">
                +{decision.rejected_alternatives.length - 12} more
              </li>
            )}
          </ul>
        </div>
      )}

      {/* compliance gate */}
      <div>
        <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-text-muted">
          Compliance clauses satisfied
        </h4>
        <div className="flex flex-wrap gap-1.5">
          {decision.clauses_satisfied.map((c) => (
            <span
              key={c.id}
              title={c.citation}
              className="inline-flex items-center gap-1 rounded-full bg-status-good/15 px-2 py-0.5 text-[11px] font-medium text-status-good"
            >
              <span className="h-1.5 w-1.5 rounded-full bg-status-good" />
              {c.id}
            </span>
          ))}
          {decision.clauses_blocked.map((c) => (
            <span
              key={c.id}
              title={c.citation}
              className="inline-flex items-center gap-1 rounded-full bg-status-critical/15 px-2 py-0.5 text-[11px] font-medium text-status-critical"
            >
              <span className="h-1.5 w-1.5 rounded-full bg-status-critical" />
              {c.id}
            </span>
          ))}
        </div>
      </div>

      <details className="text-xs">
        <summary className="cursor-pointer text-text-muted hover:text-text-secondary">
          Full audit record (SAW / THOUGHT / ALT / GATE / DID / WHY)
        </summary>
        <pre className="mt-2 max-h-96 overflow-auto whitespace-pre-wrap rounded-md bg-surface-0 p-3 text-[11px] leading-relaxed text-text-secondary">
          {decision.audit_text}
        </pre>
      </details>
    </Card>
  );
}

function Term({
  label,
  value,
  emphasize,
}: {
  label: string;
  value: string;
  emphasize?: "good" | "critical";
}) {
  const cls =
    emphasize === "good"
      ? "text-status-good"
      : emphasize === "critical"
        ? "text-status-critical"
        : "text-text-primary";
  return (
    <div className="flex items-baseline justify-between gap-2">
      <span className="text-text-muted">{label}</span>
      <span className={`tabular-nums font-medium ${cls}`}>{value}</span>
    </div>
  );
}
