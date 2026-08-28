import { notFound } from "next/navigation";
import { getAllMandateIds, getMandateAudit, getQueueItemSummaryByMandate } from "@/lib/server-data";
import { SectionHeading, Card, StatTile } from "@/components/ui";
import { formatInr } from "@/lib/format";
import { MandateTimeline } from "@/components/timeline/MandateTimeline";

export function generateStaticParams() {
  return getAllMandateIds().map((id) => ({ id: String(id) }));
}

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

  const cycleCount = new Set(records.map((r) => r.cycle_index)).size;
  const notificationCount = records.filter((r) => r.chosen.notice_at).length;
  const terminal = records[records.length - 1];

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

      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        <StatTile
          label="Decisions"
          value={String(records.length)}
          size="compact"
          source="this mandate's full audit trail"
          noCi="a count, not a statistical estimate"
        />
        <StatTile
          label="Cycles"
          value={String(cycleCount)}
          size="compact"
          source="this mandate's full audit trail"
          noCi="a count, not a statistical estimate"
        />
        <StatTile
          label="Notifications sent"
          value={String(notificationCount)}
          size="compact"
          source="attempts whose chosen action carried a pre-debit notice"
          noCi="a count, not a statistical estimate"
        />
        <StatTile
          label="Ended in"
          value={terminal.chosen.action_type.replace(/_/g, " ")}
          size="compact"
          source="this mandate's last recorded decision"
          noCi="a category, not a statistical estimate"
        />
      </div>

      {convergedDay !== undefined && (
        <Card className="text-sm">
          <span className="font-semibold text-arm-dobara-text">Converged</span> to preferred
          debit day <span className="tabular-nums font-semibold">{convergedDay}</span> of
          the month after {preferredDayChanges.length} date-change offer
          {preferredDayChanges.length > 1 ? "s" : ""}.
        </Card>
      )}

      <Card>
        <MandateTimeline records={records} />
      </Card>
    </div>
  );
}
