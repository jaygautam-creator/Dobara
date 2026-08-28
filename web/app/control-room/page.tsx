import {
  getApprovals,
  getAskWhy,
  getCounters,
  getQueueRows,
  getTopCaseFull,
} from "@/lib/server-data";
import { ControlRoomClient } from "@/components/control-room/ControlRoomClient";
import { SectionHeading } from "@/components/ui";

export const metadata = { title: "Control Room — Dobara" };

export default function ControlRoomPage() {
  const rows = getQueueRows();
  const counters = getCounters();
  const topCase = getTopCaseFull();
  const approvals = getApprovals();

  if (!topCase) {
    return (
      <div className="mx-auto max-w-3xl px-6 py-20 text-sm text-text-secondary">
        No demo batch found. Run <code>make demo-fixture</code> (or <code>make train</code>{" "}
        then start the app with a live DB) first.
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-6xl space-y-6 px-6 py-10">
      <SectionHeading
        eyebrow="Control Room"
        title="Live batch execution"
        description="One demo population, run through dobara's real decide() — every number below is genuine model output."
      />
      <ControlRoomClient
        rows={rows}
        counters={counters}
        topCaseDecision={topCase.decision}
        topCaseAskWhy={getAskWhy(
          topCase.mandate_id,
          topCase.decision.cycle_index,
          topCase.decision.attempt_index,
        )}
        approvals={approvals}
      />
      <p className="border-t border-border pt-4 text-xs text-text-muted">
        <strong>Precomputed, not live:</strong> this deploy is a static site reading{" "}
        <code>artifacts/demo_batch.json</code>, committed real <code>agent.decide()</code>{" "}
        output built by <code>make demo-fixture</code> against a trained model — not a
        mock, and no less real for having been computed earlier. Run{" "}
        <code>make api</code> locally with a trained <code>data/dobara.sqlite3</code> for
        the live decision loop.
      </p>
    </div>
  );
}
