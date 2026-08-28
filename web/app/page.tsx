import Link from "next/link";
import { Demonstration } from "@/components/home/Demonstration";
import { Equation } from "@/components/home/Equation";
import { getHomeDemo } from "@/lib/server-data";
import { formatInr } from "@/lib/format";

// docs/10-REDESIGN.md §4 `/` -- an editorial argument in five beats: the claim, the
// demonstration, the three sourced facts, the equation, the way in.

export default function ThesisPage() {
  const demo = getHomeDemo();
  const advantage = demo.selection.net_ltv_advantage_inr;

  return (
    <div className="flex flex-col">
      {/* 1 — the claim */}
      <section className="mx-auto w-full max-w-6xl px-6 pb-16 pt-20 sm:pt-28">
        <p className="text-xs font-medium uppercase tracking-[0.2em] text-arm-dobara">
          Razorpay AI Buildathon — Track 03: AI Revenue Recovery
        </p>
        <h1 className="mt-6 max-w-4xl font-serif text-step-6 leading-[0.95] tracking-tight text-text-primary">
          Every retry is a bet.
          <br />
          <span className="text-text-secondary">Dobara knows when to stop.</span>
        </h1>
        <div className="mt-10 h-px w-24 bg-arm-dobara" />
        <p className="mt-6 max-w-2xl text-step-1 leading-relaxed text-text-secondary">
          In India a retry cannot be silent: every attempt on a recurring mandate must
          carry its own pre-debit notification, at least 24 hours ahead. So the standard
          dunning playbook — retry, and retry, and retry — is a legally-mandated stream of
          messages telling a customer this merchant keeps failing to take their money. The
          failed debit is not the loss. It is the trigger.
        </p>
        <p className="mt-8 font-serif text-step-3 italic text-text-primary">
          “Recover the payment. Keep the mandate.”
        </p>
      </section>

      {/* 2 — the demonstration */}
      <section className="border-y border-border bg-surface-1/40">
        <div className="mx-auto w-full max-w-6xl px-6 py-16">
          <p className="text-xs font-medium uppercase tracking-wider text-text-muted">
            Watch it happen
          </p>
          <h2 className="mt-2 max-w-3xl font-serif text-step-4 leading-tight text-text-primary">
            The same mandate, under two policies.
          </h2>
          <p className="mt-3 max-w-2xl text-sm leading-relaxed text-text-secondary">
            Both lanes run on one shared clock, from the same simulated population and the
            same seed. Every beat, timestamp and rupee figure below is read from the
            recorded run — none of it is staged.
          </p>
          <div className="mt-8">
            <Demonstration demo={demo} />
          </div>
          <p className="mt-6 max-w-3xl text-xs leading-relaxed text-text-muted">
            Chosen mechanically, and deliberately not the best case:{" "}
            <span className="tabular-nums">
              {demo.selection.n_candidates.toLocaleString("en-IN")}
            </span>{" "}
            of the{" "}
            <span className="tabular-nums">
              {demo.selection.n_mandates.toLocaleString("en-IN")}
            </span>{" "}
            mandates in this held-out population (seed{" "}
            <span className="tabular-nums">{demo.seed}</span>) revoked under the aggressive
            policy but survived under Dobara. The one shown is the{" "}
            <strong className="text-text-secondary">median</strong> of those by net
            lifetime value kept — the middle case, not the flattering one. Across that
            set, Dobara&apos;s advantage per mandate runs from{" "}
            <span className="tabular-nums">{formatInr(advantage.p25)}</span> at the 25th
            percentile to <span className="tabular-nums">{formatInr(advantage.p75)}</span>{" "}
            at the 75th, with a median of{" "}
            <span className="tabular-nums">{formatInr(advantage.median)}</span>. Population-
            level results, with confidence intervals and every arm, are on{" "}
            <Link href="/evidence" className="underline decoration-dotted underline-offset-2">
              Evidence
            </Link>
            .
          </p>
        </div>
      </section>

      {/* 3 — the three sourced facts, as a band */}
      <section className="mx-auto w-full max-w-6xl px-6 py-16">
        <div className="grid gap-8 sm:grid-cols-3">
          <Fact
            number="20M+"
            claim="UPI AutoPay mandates are revoked every month in India."
            source="Business Standard, 2025"
            href="https://www.business-standard.com/finance/news/upi-autopay-revocations-hit-20-mn-monthly-over-low-customer-balances-125090700500_1.html"
          />
          <Fact
            number="24h"
            claim="Minimum notice before every debit attempt, retries included. No exceptions, no silent retry."
            source="RBI e-mandate framework — docs/01-REGULATORY.md"
            href="/architecture"
          />
          <Fact
            number="8×"
            claim="Retries the standard playbook allows — which is eight mandatory messages about a merchant who keeps failing."
            source="docs/01-REGULATORY.md"
            href="/architecture"
          />
        </div>
      </section>

      {/* 4 — the equation */}
      <section className="border-y border-border bg-surface-1/40">
        <div className="mx-auto grid w-full max-w-6xl gap-10 px-6 py-16 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
          <div>
            <p className="text-xs font-medium uppercase tracking-wider text-text-muted">
              Therefore
            </p>
            <h2 className="mt-2 font-serif text-step-4 leading-tight text-text-primary">
              Price the retry, not just the recovery.
            </h2>
            <p className="mt-4 text-step-0 leading-relaxed text-text-secondary">
              Because every attempt forces a notification, the cost lands whether or not
              the debit succeeds. That inverts the industry default: fewer, better-placed
              attempts beat many attempts. Dobara scores every legal action at every legal
              time against one expression, and refuses to act when the expression says the
              bet is not worth taking.
            </p>
            <p className="mt-4 text-step-0 leading-relaxed text-text-secondary">
              No language model is anywhere in this arithmetic — a boundary a test
              enforces, not a promise a prompt makes. See{" "}
              <Link
                href="/architecture"
                className="underline decoration-dotted underline-offset-2"
              >
                Architecture
              </Link>
              .
            </p>
          </div>
          <Equation />
        </div>
      </section>

      {/* 5 — the way in */}
      <section className="mx-auto w-full max-w-6xl px-6 py-16">
        <div className="grid gap-4 sm:grid-cols-3">
          <EntryPoint
            href="/control-room"
            label="Control Room"
            description="A real batch of decisions, ranked by rupees at risk, each one openable down to the arithmetic."
          />
          <EntryPoint
            href="/evidence"
            label="Evidence"
            description="Five arms, thirty seeds, 95% confidence intervals, a permanent holdout, and what would have to be true for the result to flip."
          />
          <EntryPoint
            href="/architecture"
            label="Architecture"
            description="The system diagram, the wall the language model cannot cross, and the compliance gate that makes illegal actions unrepresentable."
          />
        </div>
      </section>
    </div>
  );
}

function Fact({
  number,
  claim,
  source,
  href,
}: {
  number: string;
  claim: string;
  source: string;
  href: string;
}) {
  const external = href.startsWith("http");
  return (
    <div className="border-t border-border pt-5">
      <div className="tabular-nums text-step-5 font-semibold leading-none text-arm-dobara">
        {number}
      </div>
      <p className="mt-3 text-step-0 leading-relaxed text-text-primary">{claim}</p>
      <a
        href={href}
        target={external ? "_blank" : undefined}
        rel={external ? "noreferrer" : undefined}
        className="mt-3 inline-block text-[11px] text-text-muted underline decoration-dotted underline-offset-2"
      >
        {source}
      </a>
    </div>
  );
}

function EntryPoint({
  href,
  label,
  description,
}: {
  href: string;
  label: string;
  description: string;
}) {
  return (
    <Link
      href={href}
      className="group rounded-lg border border-border bg-surface-1 p-5 transition-colors hover:border-arm-dobara/50 hover:bg-surface-2"
    >
      <div className="flex items-baseline justify-between">
        <span className="text-sm font-semibold text-text-primary">{label}</span>
        <span className="text-text-muted transition-transform group-hover:translate-x-0.5">→</span>
      </div>
      <p className="mt-2 text-sm leading-relaxed text-text-secondary">{description}</p>
    </Link>
  );
}
