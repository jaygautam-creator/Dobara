import { notFound } from "next/navigation";
import { getAllMandateIds, getMandateAudit, getQueueItemSummaryByMandate } from "@/lib/server-data";
import { DecisionCard } from "@/components/DecisionCard";
import { SectionHeading } from "@/components/ui";

export function generateStaticParams() {
  return getAllMandateIds().map((id) => ({ id: String(id) }));
}

export default async function AuditPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const mandateId = Number(id);
  const records = getMandateAudit(mandateId);
  if (!records) notFound();

  const summary = getQueueItemSummaryByMandate(mandateId);

  return (
    <div className="mx-auto max-w-4xl space-y-8 px-6 py-10">
      <SectionHeading
        eyebrow="Audit trail"
        title={`Mandate #${mandateId}`}
        description={
          summary
            ? `${summary.bank_id} · ${summary.method} · ${summary.merchant_category} — every decision made for this mandate, in order.`
            : "Every decision made for this mandate, in order."
        }
      />
      <div className="space-y-6">
        {records.map((decision, i) => (
          <DecisionCard key={i} decision={decision} />
        ))}
      </div>
    </div>
  );
}
