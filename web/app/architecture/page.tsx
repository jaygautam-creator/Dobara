import { ComplianceGateSequence } from "@/components/architecture/ComplianceGateSequence";
import { DecisionWalkthrough } from "@/components/architecture/DecisionWalkthrough";
import { SystemDiagram } from "@/components/architecture/SystemDiagram";
import { GITHUB_BLOB } from "@/components/architecture/nodes";
import { Card, SectionHeading } from "@/components/ui";
import { getComplianceRules, getFeaturedDecisions } from "@/lib/server-data";

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
  const featured = getFeaturedDecisions();

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

      <section id="watch-it-decide" className="scroll-mt-20">
        <SectionHeading
          eyebrow="Watch it decide"
          title="One real decision, walked stage by stage"
          description="Every figure below is read from artifacts/demo_batch.json — the same fixture the Control Room and every /audit page read, not staged for this component."
        />
        <DecisionWalkthrough cases={featured} rules={compliance.rules} />
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

      <section id="how-this-is-used" className="scroll-mt-20">
        <SectionHeading
          eyebrow="Adoption"
          title="How anyone would actually use this"
          description="Not a payment aggregator. Dobara proposes; a licensed PA executes. No funds are handled."
        />
        <div className="grid gap-4 sm:grid-cols-2">
          <Card variant="raised">
            <h3 className="text-sm font-semibold text-text-primary">Merchant</h3>
            <p className="mt-2 text-sm leading-relaxed text-text-secondary">
              Points Razorpay <code className="font-mono text-xs">payment.failed</code>{" "}
              webhooks in, reads a proposal queue out — no change to the existing Razorpay
              integration. Above ₹15,000 a decision routes to a human sign-off instead of
              executing (<code className="font-mono text-xs">requires_signoff</code> in{" "}
              <a
                href={`${GITHUB_BLOB}/agent/decide.py`}
                target="_blank"
                rel="noreferrer"
                className="underline decoration-dotted underline-offset-2"
              >
                agent/decide.py
              </a>
              ), which is also the realistic adoption path: start with approve-everything,
              loosen the threshold as trust builds.
            </p>
          </Card>
          <Card variant="raised">
            <h3 className="text-sm font-semibold text-text-primary">Razorpay</h3>
            <p className="mt-2 text-sm leading-relaxed text-text-secondary">
              The rail and the data source: signature-verified webhooks in, proposals out —
              never a direct rail call. And it is honest about what it doesn&apos;t have:{" "}
              <a
                href={`${GITHUB_BLOB}/api/razorpay_client.py`}
                target="_blank"
                rel="noreferrer"
                className="font-mono underline decoration-dotted underline-offset-2"
              >
                api/razorpay_client.py
              </a>{" "}
              is credential-optional by design — with no keys it raises{" "}
              <code className="font-mono text-xs">RazorpayNotConfigured</code> rather than
              faking a success. Most submissions silently no-op instead; this one refuses to.
            </p>
          </Card>
          <Card variant="raised" className="sm:col-span-2">
            <h3 className="text-sm font-semibold text-text-primary">Customer</h3>
            <p className="mt-2 text-sm leading-relaxed text-text-secondary">
              Never sees Dobara. No app, no login, no message from Dobara. The only things
              ever addressed to them are the legally-mandated pre-debit notice and,
              occasionally, one offer to move the debit date. The product&apos;s success
              condition is that the customer notices nothing.
            </p>
          </Card>
        </div>
      </section>

      <section id="what-it-refuses" className="scroll-mt-20">
        <SectionHeading
          eyebrow="Refuse"
          title="What it refuses to look at"
          description="A build-time guard, not just a promise: importing features/recovery.py fails immediately if any feature name encodes an individual's finances."
        />
        <Card variant="raised">
          <p className="text-sm leading-relaxed text-text-secondary">
            <a
              href={`${GITHUB_BLOB}/features/recovery.py`}
              target="_blank"
              rel="noreferrer"
              className="font-mono underline decoration-dotted underline-offset-2"
            >
              features/recovery.py
            </a>
            &apos;s <code className="font-mono text-xs">assert_no_banned_features()</code>{" "}
            raises at import time if any feature name contains{" "}
            <code className="font-mono text-xs">
              balance · income · cashflow · spend · salary
            </code>
            . What the models see instead: this bank&apos;s recent health, this mandate&apos;s
            own failure history, timing in the billing cycle, and amount band relative to the
            AFA threshold — the payments rail, not a profile of the person behind it.
          </p>
        </Card>
      </section>

      <section id="not-built-yet" className="scroll-mt-20">
        <SectionHeading
          eyebrow="Honest boundary"
          title="What is not built"
          description="Stated before a judge finds it, not after."
        />
        <Card variant="raised">
          <p className="text-sm leading-relaxed text-text-secondary">
            The webhook receiver and the decision engine both exist and are real —{" "}
            <a
              href={`${GITHUB_BLOB}/api/main.py`}
              target="_blank"
              rel="noreferrer"
              className="font-mono underline decoration-dotted underline-offset-2"
            >
              api/main.py
            </a>{" "}
            verifies each webhook&apos;s signature and acknowledges it — but the queue that
            would connect one to the other is scaffolded, not production: the endpoint is
            intake-only and does not re-trigger a decision pass on its own. And the deployed
            site you are reading is a static export of a real recorded batch run, not a
            server making live decisions at request time — nowhere on this site should the
            Control Room be described as &ldquo;live.&rdquo;
          </p>
        </Card>
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

      <section>
        <SectionHeading
          eyebrow="Note"
          title="Built solo, for this buildathon"
          description="A few sentences from the person who built it."
        />
        <p className="max-w-2xl text-sm leading-relaxed text-text-secondary">
          I&apos;m Jay Gautam, and I built Dobara alone for this submission. The rewiring in{" "}
          <a
            href={`${GITHUB_BLOB}/agent/decide.py`}
            target="_blank"
            rel="noreferrer"
            className="font-mono underline decoration-dotted underline-offset-2"
          >
            agent/decide.py
          </a>{" "}
          on this page is the thing I&apos;m most honest about: 76% of decisions were tying
          exactly at the argmax, silently resolved by loop order rather than any real rule.
          I diagnosed it before touching the fix, found the real cause (a too-coarse
          probability calibrator flattening a signal the model had genuinely learned), and
          committed to reporting the headline number honestly either way before rerunning
          — it moved by ₹0.28/mandate the first time, not a regression, but I didn&apos;t
          know that going in. The second time was a bigger test of that same commitment:
          a follow-up bake-off found a continuous calibrator (Platt scaling) that cut the
          tie rate from ~77% to ~16-18%, measured directly against the pre-registered
          bar, and adopting it was the pre-registered right call — but it reversed the
          headline from a +₹65.71/mandate win to a −₹64.09/mandate loss. I kept the
          calibrator and reported the loss at full weight rather than reverting or
          hunting a better number; the current headline on this site reflects that loss,
          not the earlier win. Full account, dated, in{" "}
          <a
            href={`${GITHUB_BLOB}/docs/DECISIONS.md`}
            target="_blank"
            rel="noreferrer"
            className="font-mono underline decoration-dotted underline-offset-2"
          >
            docs/DECISIONS.md
          </a>
          .
        </p>
      </section>
    </div>
  );
}
