import { notFound } from "next/navigation";
import { getAllMandateIds, getMandateAudit, getQueueItemSummaryByMandate } from "@/lib/server-data";
import { SectionHeading, Badge, Card } from "@/components/ui";
import { formatInr } from "@/lib/format";

export function generateStaticParams() {
  return getAllMandateIds().map((id) => ({ id: String(id) }));
}

const ACTION_COLOR: Record<string, string> = {
  schedule_debit: "bg-status-good",
  offer_date_change: "bg-arm-dobara",
  stop: "bg-text-muted",
  abstain: "bg-status-warning",
  escalate_to_human: "bg-status-critical",
};

export default async function MandateTimelinePage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const mandateId = Number(id);
  const records = getMandateAudit(mandateId);
  if (!records) notFound();
  const summary = getQueueItemSummaryByMandate(mandateId);

  const byCycle = new Map<number, typeof records>();
  for (const r of records) {
    const list = byCycle.get(r.cycle_index) ?? [];
    list.push(r);
    byCycle.set(r.cycle_index, list);
  }
  const cycles = Array.from(byCycle.keys()).sort((a, b) => a - b);

  const preferredDayChanges = records
    .map((r) => r.chosen.new_preferred_day)
    .filter((d): d is number => d != null);
  const convergedDay = preferredDayChanges.at(-1);

  return (
    <div className="mx-auto max-w-5xl space-y-8 px-6 py-10">
      <SectionHeading
        eyebrow="Mandate timeline"
        title={`Mandate #${mandateId}`}
        description={
          summary
            ? `${summary.bank_id} · ${summary.method} · ${formatInr(summary.amount)} · ${summary.merchant_category}`
            : undefined
        }
      />

      {convergedDay !== undefined && (
        <Card className="text-sm">
          <span className="font-semibold text-arm-dobara">Converged</span> to preferred
          debit day <span className="tabular-nums font-semibold">{convergedDay}</span> of
          the month after {preferredDayChanges.length} date-change offer
          {preferredDayChanges.length > 1 ? "s" : ""}.
        </Card>
      )}

      <div>
        <div className="flex flex-wrap gap-4 pb-4">
          {cycles.map((cycle) => (
            <div key={cycle} className="w-40 shrink-0">
              <div className="mb-2 text-xs font-medium uppercase tracking-wide text-text-muted">
                Cycle {cycle}
              </div>
              <div className="space-y-2 border-l-2 border-gridline pl-3">
                {(byCycle.get(cycle) ?? []).map((r, i) => (
                  <div key={i} className="relative">
                    <span
                      className={`absolute -left-[17px] top-1 h-2.5 w-2.5 rounded-full ${
                        ACTION_COLOR[r.chosen.action_type] ?? "bg-text-muted"
                      }`}
                    />
                    <div className="rounded-md border border-border bg-surface-1 p-2">
                      <div className="tabular-nums text-[11px] font-medium text-text-primary">
                        attempt {r.attempt_index}
                      </div>
                      <Badge>{r.chosen.action_type}</Badge>
                      <div className="mt-1 tabular-nums text-[11px] text-text-secondary">
                        {formatInr(r.expected_net)}
                      </div>
                      {r.chosen.notice_at && (
                        <div className="tabular-nums mt-0.5 break-words text-[10px] text-text-muted">
                          notice {new Date(r.chosen.notice_at).toLocaleDateString("en-IN")}
                        </div>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
