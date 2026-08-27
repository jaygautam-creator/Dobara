import Link from "next/link";

export default function ThesisPage() {
  return (
    <div className="mx-auto flex max-w-4xl flex-col gap-14 px-6 py-20">
      <section>
        <p className="mb-4 text-sm font-medium uppercase tracking-wider text-arm-dobara">
          Razorpay AI Buildathon — Track 03: AI Revenue Recovery
        </p>
        <h1 className="text-4xl font-semibold leading-tight tracking-tight text-text-primary sm:text-5xl">
          Every retry is a bet.
          <br />
          <span className="text-text-secondary">Dobara knows when to stop.</span>
        </h1>
        <p className="mt-6 max-w-2xl text-lg leading-relaxed text-text-secondary">
          An AI revenue-recovery agent for Indian recurring payments.
        </p>
      </section>

      <section className="grid gap-6 sm:grid-cols-3">
        <FactCard
          number="20M+"
          label="UPI AutoPay mandates revoked every month, India"
          source="business-standard.com, 2025"
          href="https://www.business-standard.com/finance/news/upi-autopay-revocations-hit-20-mn-monthly-over-low-customer-balances-125090700500_1.html"
        />
        <FactCard
          number="24h"
          label="Mandatory pre-debit notification before every retry — no exceptions"
          source="RBI e-mandate framework"
          href="/evidence"
        />
        <FactCard
          number="8x"
          label="Retries the standard playbook allows — 8 mandatory warnings that this merchant keeps failing"
          source="docs/01-REGULATORY.md"
          href="/evidence"
        />
      </section>

      <section className="space-y-4 border-l-2 border-arm-dobara pl-6">
        <p className="text-lg leading-relaxed text-text-primary">
          The failed debit is not the loss. <strong>It is the trigger.</strong> Debit fails
          → customer is notified → customer opens their UPI app and kills the mandate →
          the merchant loses not this month&apos;s payment, but every future one.
        </p>
        <p className="text-lg leading-relaxed text-text-primary">
          In India, a retry cannot be silent. It cannot be faster than 24 hours. And{" "}
          <strong>eight retries means eight mandatory messages</strong> telling a customer
          this merchant keeps failing to take their money. The standard dunning
          playbook — retry aggressively, up to eight attempts — is, under Indian
          regulation, a legally-mandated harassment machine. The regulator forced the
          retry to be loud, and nobody redesigned the strategy around it.
        </p>
      </section>

      <section className="rounded-xl border border-border bg-surface-1 p-8">
        <p className="text-sm font-medium uppercase tracking-wider text-text-muted">
          Therefore
        </p>
        <p className="mt-2 text-xl font-medium leading-snug text-text-primary">
          Every retry is a bet with downside. Retrying harder can lose more money than
          not retrying at all.
        </p>
        <pre className="mt-6 overflow-x-auto rounded-lg bg-surface-0 p-4 text-sm leading-relaxed text-text-secondary">
{`E[net | action] = P(success | t) × amount
                − P(revoke | attempts+1, contacts) × LTV_remaining
                − cost(channel)`}
        </pre>
        <p className="mt-4 text-sm leading-relaxed text-text-secondary">
          Dobara acts on the argmax, and stops when the expression goes negative — a
          stopping rule with a rupee behind it, not an arbitrary attempt cap.
        </p>
      </section>

      <section className="text-center">
        <p className="text-2xl font-medium italic text-text-primary">
          &ldquo;Recover the payment. Keep the mandate.&rdquo;
        </p>
        <div className="mt-8 flex justify-center gap-3">
          <Link
            href="/control-room"
            className="rounded-md bg-arm-dobara px-6 py-3 text-sm font-semibold text-white transition-opacity hover:opacity-90"
          >
            Open the Control Room
          </Link>
          <Link
            href="/evidence"
            className="rounded-md border border-border px-6 py-3 text-sm font-semibold text-text-primary transition-colors hover:bg-surface-1"
          >
            See the evidence
          </Link>
        </div>
      </section>
    </div>
  );
}

function FactCard({
  number,
  label,
  source,
  href,
}: {
  number: string;
  label: string;
  source: string;
  href: string;
}) {
  return (
    <a
      href={href}
      target={href.startsWith("http") ? "_blank" : undefined}
      rel={href.startsWith("http") ? "noreferrer" : undefined}
      className="block rounded-lg border border-border bg-surface-1 p-5 transition-colors hover:bg-surface-2"
    >
      <div className="tabular-nums text-3xl font-semibold text-arm-dobara">{number}</div>
      <p className="mt-2 text-sm leading-snug text-text-secondary">{label}</p>
      <p className="mt-2 text-[11px] text-text-muted underline decoration-dotted">
        {source}
      </p>
    </a>
  );
}
