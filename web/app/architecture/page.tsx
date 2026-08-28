import { ComplianceGateSequence } from "@/components/architecture/ComplianceGateSequence";
import { SystemDiagram } from "@/components/architecture/SystemDiagram";
import { GITHUB_BLOB } from "@/components/architecture/nodes";
import { Card, SectionHeading } from "@/components/ui";
import { getComplianceRules } from "@/lib/server-data";

export const metadata = { title: "Architecture — Dobara" };

const STOPPING_REASONS: [string, string][] = [
  ["hard_decline", "the decline reason is terminal; retrying cannot help"],
  ["mandate_revoked", "nothing left to recover against"],
  ["customer_opted_out", "the customer used the control we gave them"],
  ["max_attempts", "the configured cap for this cycle"],
  ["cost_cap", "cumulative recovery spend exceeded its budget"],
  [
    "negative_expected_value",
    "the derived one — expected recovery no longer exceeds expected revocation cost",
  ],
  ["insufficient_confidence", "the models abstained; the agent does not guess"],
];

export default function ArchitecturePage() {
  const compliance = getComplianceRules();

  return (
    <div className="mx-auto max-w-6xl space-y-14 px-6 py-14">
      <header>
        <p className="text-xs font-medium uppercase tracking-wider text-arm-dobara-text">
          Architecture
        </p>
        <h1 className="mt-2 max-w-3xl font-serif text-step-5 leading-[1.05] text-text-primary">
          A wall runs through this system.
        </h1>
        <p className="mt-5 max-w-2xl text-step-1 leading-relaxed text-text-secondary">
          Dobara decides with money on the line, so the components that touch that decision
          are tabular, calibrated and inspectable — and the language model is kept on the
          other side of a boundary that a test enforces. Select any box to see what it owns
          and open its source.
        </p>
      </header>

      <section>
        <SystemDiagram />
      </section>

      <section>
        <SectionHeading
          eyebrow="Execute"
          title="The compliance gate is structural"
          description="An action that would breach an RBI, TRAI, NPCI or DPDP rule is not scored and rejected — it is never in the candidate set to begin with."
        />
        <ComplianceGateSequence
          rules={compliance.rules}
          nHard={compliance.n_hard}
          nSoft={compliance.n_soft}
        />
        <p className="mt-3 text-xs text-text-muted">
          Rule list exported directly from{" "}
          <a
            href={`${GITHUB_BLOB}/agent/compliance.py`}
            target="_blank"
            rel="noreferrer"
            className="font-mono underline decoration-dotted underline-offset-2"
          >
            agent/compliance.py
          </a>{" "}
          at build time — this page cannot drift from the gate it describes. Generated at{" "}
          <span className="tabular-nums">
            {compliance.provenance.generated_at.slice(0, 19).replace("T", " ")} UTC
          </span>{" "}
          from
          commit{" "}
          <span className="tabular-nums">
            {compliance.provenance.git_commit.slice(0, 12)}
          </span>
          .
        </p>
      </section>

      <section>
        <SectionHeading
          eyebrow="Stop"
          title="Seven named reasons, one of which is the whole thesis"
          description="Every stop the agent makes names exactly one reason, and it appears in the audit trail and in the UI."
        />
        <Card variant="raised" className="divide-y divide-border p-0">
          {STOPPING_REASONS.map(([id, text]) => (
            <div key={id} className="flex flex-col gap-1 p-4 sm:flex-row sm:items-baseline sm:gap-4">
              <span className="tabular-nums w-64 shrink-0 text-sm font-semibold text-text-primary">
                {id}
              </span>
              <span className="text-sm leading-relaxed text-text-secondary">{text}</span>
            </div>
          ))}
        </Card>
      </section>
    </div>
  );
}
