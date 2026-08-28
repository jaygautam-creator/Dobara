"use client";

import { useState } from "react";

// docs/10-REDESIGN.md §4 `/` beat 4: the decision rule as a typeset display object with
// each term annotated on hover/tap -- not a <pre> block. The expression itself is
// docs/02-ARCHITECTURE.md "## The decision, formally", and each annotation names the
// component that actually computes that term.

interface Term {
  id: string;
  render: string;
  title: string;
  body: string;
  file: string;
  tone: "gain" | "loss" | "cost";
}

const TERMS: Term[] = [
  {
    id: "recover",
    render: "P(success | t) × amount",
    title: "What a retry might win",
    body: "The calibrated probability that a debit attempted at time t succeeds, times the rupees at stake. This is the only term the industry's standard playbook optimises.",
    file: "models/recovery.py",
    tone: "gain",
  },
  {
    id: "revoke",
    render: "P(revoke | attempts+1, contacts) × LTV_remaining",
    title: "What the same retry risks",
    body: "The hazard that this attempt — and the notification India requires it to carry — is the one that makes the customer cancel the mandate, times every future cycle that cancellation takes with it. The hazard rises with attempt count and contact density, not merely with elapsed time.",
    file: "models/revocation.py",
    tone: "loss",
  },
  {
    id: "cost",
    render: "cost(channel)",
    title: "What it costs to ask",
    body: "The direct price of the mandated pre-debit notification on the channel chosen — small, and the least interesting of the three, but real and always paid, whether the debit succeeds or not.",
    file: "sim/params.yaml",
    tone: "cost",
  },
];

const TONE_CLASS: Record<Term["tone"], string> = {
  gain: "text-status-good-text",
  loss: "text-status-critical-text",
  cost: "text-text-secondary",
};

export function Equation() {
  const [activeId, setActiveId] = useState<string>(TERMS[0].id);
  const active = TERMS.find((t) => t.id === activeId)!;

  return (
    <div>
      <div className="tabular-nums flex flex-col gap-1 text-step-1 leading-relaxed">
        <div className="text-text-muted">
          E[net | action] <span className="text-text-secondary">=</span>
        </div>
        {TERMS.map((term, i) => (
          <div key={term.id} className="flex items-baseline gap-2 pl-6">
            <span className="w-4 shrink-0 text-text-secondary">
              {i === 0 ? "" : "−"}
            </span>
            <button
              type="button"
              onMouseEnter={() => setActiveId(term.id)}
              onFocus={() => setActiveId(term.id)}
              onClick={() => setActiveId(term.id)}
              aria-pressed={term.id === activeId}
              className={`rounded-sm px-1 text-left underline decoration-dotted underline-offset-4 transition-colors ${
                TONE_CLASS[term.tone]
              } ${term.id === activeId ? "bg-surface-2" : "hover:bg-surface-2"}`}
            >
              {term.render}
            </button>
          </div>
        ))}
      </div>

      <div className="mt-6 rounded-lg border border-border bg-surface-0 p-4" aria-live="polite">
        <div className={`text-sm font-semibold ${TONE_CLASS[active.tone]}`}>{active.title}</div>
        <p className="mt-1.5 text-sm leading-relaxed text-text-secondary">{active.body}</p>
        <p className="mt-2 font-mono text-[11px] text-text-muted">{active.file}</p>
      </div>

      <p className="mt-4 text-sm leading-relaxed text-text-secondary">
        Dobara acts on the argmax and stops when the expression turns negative — a stopping
        rule with a rupee behind it, not an arbitrary attempt cap. When the confidence
        interval around it straddles zero, it abstains rather than guesses.
      </p>
    </div>
  );
}
