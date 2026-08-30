"use client";

import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { motion, useInView } from "motion/react";
import { useStaticRender } from "@/lib/motion";
import { formatInrPrecise } from "@/lib/format";
import type { ClauseRefOut, ComplianceRule, DecisionOut, RejectedAlternativeOut } from "@/lib/types";
import { totalCandidatesConsidered } from "@/components/DecisionCard";
import { DecisionEquation } from "@/components/audit/DecisionEquation";

// docs/10-REDESIGN.md's /architecture page explains the mechanism in prose; nowhere on
// the site can a viewer watch the agent actually decide. This walks one real decision
// end to end -- situation, priced candidates, compliance clauses, arithmetic -- staged
// like components/home/Demonstration.tsx, and skippable the same way. Every figure is
// read from `demo_batch.json` via lib/server-data.ts's getFeaturedDecisions(); nothing
// here is hand-typed or re-derived beyond what DecisionCard.tsx's own
// totalCandidatesConsidered() already does elsewhere on the site.
//
// The fixture does not record how many candidates `_generate_candidates` produced or
// how many the HARD compliance gate struck out before scoring -- `clauses_blocked` is
// per-chosen-action, not a filter count. This component deliberately shows only
// rejected_alternatives, clauses_satisfied/blocked, and rupee_math: nothing here states
// or animates a "N candidates -> M legal" transition. See docs/DECISIONS.md
// [2026-08-30] "Decision walkthrough component".

const BEAT_MS = 260;
const MAX_ALTERNATIVES_SHOWN = 8;

const ACTION_LABEL: Record<string, string> = {
  schedule_debit: "Schedule debit",
  offer_date_change: "Offer date change",
  stop: "Stop",
  abstain: "Abstain",
  escalate_to_human: "Escalate to human",
};

function formatWhen(iso: string): string {
  return new Date(iso).toLocaleString("en-IN", {
    day: "numeric",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
}

type CaseKey = "stop" | "abstain";

const CASE_META: Record<CaseKey, { tabLabel: string; blurb: string }> = {
  stop: {
    tabLabel: "Stop wins at ₹0",
    blurb: "Every priced alternative this cycle came back negative -- zero beats all of them.",
  },
  abstain: {
    tabLabel: "Abstain, not guess",
    blurb: "The point estimate is positive, but its confidence band straddles zero -- so the agent declines to act rather than gamble.",
  },
};

export function DecisionWalkthrough({
  cases,
  rules,
}: {
  cases: Record<CaseKey, DecisionOut>;
  rules: ComplianceRule[];
}) {
  const [active, setActive] = useState<CaseKey>("stop");
  const decision = cases[active];
  const ruleById = useMemo(() => new Map(rules.map((r) => [r.id, r])), [rules]);

  const shownAlternatives = decision.rejected_alternatives.slice(0, MAX_ALTERNATIVES_SHOWN);
  const hiddenCount = decision.rejected_alternatives.length - shownAlternatives.length;

  // Stage list: situation -> winner -> each shown alternative -> compliance clauses ->
  // arithmetic. A flat, ordered list so "reveal everything up to step N" is one filter,
  // the same pattern components/home/Demonstration.tsx uses.
  const stages = useMemo(
    () => ["situation", "winner", ...shownAlternatives.map((_, i) => `alt-${i}`), "clauses", "math"],
    [shownAlternatives],
  );
  const total = stages.length;

  const ref = useRef<HTMLDivElement>(null);
  const inView = useInView(ref, { once: false, amount: 0.25 });

  const isStatic = useStaticRender();
  const [liveStep, setLiveStep] = useState(0);
  const step = isStatic ? total : liveStep;
  const done = step >= total;

  useEffect(() => {
    if (isStatic || !inView || liveStep >= total) return;
    const timer = setTimeout(() => setLiveStep((s) => s + 1), BEAT_MS);
    return () => clearTimeout(timer);
  }, [isStatic, inView, liveStep, total]);

  function reset(key: CaseKey) {
    setActive(key);
    setLiveStep(isStatic ? total : 0);
  }

  return (
    <div ref={ref}>
      <div className="mb-4 flex flex-wrap items-center gap-2">
        {(Object.keys(CASE_META) as CaseKey[]).map((key) => (
          <button
            key={key}
            type="button"
            onClick={() => reset(key)}
            className={`rounded-md border px-3 py-1.5 text-xs font-semibold transition-colors ${
              active === key
                ? "border-arm-dobara bg-arm-dobara/15 text-arm-dobara-text"
                : "border-border text-text-secondary hover:bg-surface-1"
            }`}
          >
            {CASE_META[key].tabLabel}
          </button>
        ))}
      </div>
      <p className="mb-4 max-w-2xl text-sm leading-relaxed text-text-secondary">
        {CASE_META[active].blurb}
      </p>

      <div
        className="rounded-lg border border-border bg-surface-1 p-5"
        onClick={() => {
          if (!done) setLiveStep(total);
        }}
      >
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="tabular-nums text-xs uppercase tracking-wide text-text-muted">
            Mandate #{decision.mandate_id} · cycle {decision.cycle_index} · attempt{" "}
            {decision.attempt_index} · {formatWhen(decision.now)}
          </div>
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              setLiveStep(done ? 0 : total);
            }}
            disabled={isStatic}
            className="rounded-md border border-border px-3 py-1.5 text-xs font-medium text-text-secondary transition-colors hover:bg-surface-1 hover:text-text-primary"
          >
            {done ? "Replay" : "Skip to the end"}
          </button>
        </div>

        <Reveal show={step >= 1}>
          <div className="mt-4 grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
            <Fact label="Bank" value={decision.bank_id} />
            <Fact label="Method" value={decision.method} />
            <Fact label="Amount" value={formatInrPrecise(decision.amount)} />
            <Fact
              label="Prior failure"
              value={decision.prev_error_reason ?? "none"}
            />
          </div>
        </Reveal>

        <Reveal show={step >= 2}>
          <div className="mt-5">
            <p className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-text-muted">
              Candidates priced ({totalCandidatesConsidered(decision.rejected_alternatives)} considered)
            </p>
            <div className="space-y-1.5">
              <CandidateRow
                label={`Winner — ${ACTION_LABEL[decision.chosen.action_type] ?? decision.chosen.action_type}`}
                expectedNet={decision.expected_net}
                detail={decision.chosen.stop_reason ?? decision.chosen.abstain_reason ?? undefined}
                winner
                show={step >= 2}
              />
              {shownAlternatives.map((alt, i) => (
                <AlternativeRow key={i} alt={alt} show={step >= 3 + i} />
              ))}
              {hiddenCount > 0 && step >= total - 2 && (
                <div className="pl-3 text-[11px] text-text-muted">
                  +{totalCandidatesConsidered(decision.rejected_alternatives.slice(MAX_ALTERNATIVES_SHOWN))}{" "}
                  more candidates, in {hiddenCount} further rows not shown
                </div>
              )}
            </div>
          </div>
        </Reveal>

        <Reveal show={step >= total - 1}>
          <div className="mt-5">
            <p className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-text-muted">
              Compliance clauses the winner satisfies
            </p>
            <div className="flex flex-wrap gap-1.5">
              {decision.clauses_satisfied.map((c) => (
                <ClauseBadge key={c.id} clause={c} rule={ruleById.get(c.id)} />
              ))}
              {decision.clauses_blocked.map((c) => (
                <ClauseBadge key={c.id} clause={c} rule={ruleById.get(c.id)} blocked />
              ))}
            </div>
          </div>
        </Reveal>

        <Reveal show={step >= total}>
          <div className="mt-5">
            <p className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-text-muted">
              The winner&apos;s own arithmetic
            </p>
            <DecisionEquation rm={decision.rupee_math} />
            <div className="tabular-nums mt-2 text-[11px] text-text-muted">
              95% confidence band: [{formatInrPrecise(decision.confidence_band[0])},{" "}
              {formatInrPrecise(decision.confidence_band[1])}]
            </div>
            {decision.rupee_math.expected_net === 0 && decision.rupee_math.amount === 0 && (
              <p className="mt-2 max-w-xl text-xs italic leading-relaxed text-text-secondary">
                {ACTION_LABEL[decision.chosen.action_type]} makes no attempt, so its own
                arithmetic is zero by definition -- every real alternative priced above it
                came back negative.
              </p>
            )}
          </div>
        </Reveal>
      </div>
    </div>
  );
}

// Deliberately not an unmount/height-collapse: every stage's block stays in the layout
// once it has ever been shown, so revealing the next stage never has to re-measure or
// jump the ones above it -- the same stable-layout, opacity-only approach
// components/home/Demonstration.tsx uses for its own beat list.
function Reveal({ show, children }: { show: boolean; children: ReactNode }) {
  return (
    <motion.div
      initial={false}
      animate={{ opacity: show ? 1 : 0 }}
      transition={{ duration: BEAT_MS / 1000, ease: [0.2, 0, 0, 1] }}
      aria-hidden={!show}
      className={show ? "" : "pointer-events-none select-none"}
    >
      {children}
    </motion.div>
  );
}

function Fact({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border border-border bg-surface-0 p-2.5">
      <div className="text-[10px] uppercase tracking-wide text-text-muted">{label}</div>
      <div className="mt-0.5 truncate text-sm font-medium text-text-primary">{value}</div>
    </div>
  );
}

function CandidateRow({
  label,
  expectedNet,
  detail,
  winner,
  show,
}: {
  label: string;
  expectedNet: number;
  detail?: string;
  winner?: boolean;
  show: boolean;
}) {
  return (
    <motion.div
      initial={false}
      animate={{ opacity: show ? 1 : 0, x: show ? 0 : -6 }}
      transition={{ duration: 0.22, ease: [0.2, 0, 0, 1] }}
      className={`flex items-baseline justify-between gap-3 rounded-md border px-3 py-2 text-xs ${
        winner ? "border-arm-dobara/50 bg-arm-dobara/10" : "border-border"
      }`}
    >
      <span className={winner ? "font-semibold text-arm-dobara-text" : "text-text-secondary"}>
        {label}
        {detail && <span className="ml-1.5 text-text-muted">({detail.replaceAll("_", " ")})</span>}
      </span>
      <span
        className={`tabular-nums shrink-0 font-medium ${
          expectedNet > 0
            ? "text-status-good-text"
            : expectedNet < 0
              ? "text-status-critical-text"
              : "text-text-secondary"
        }`}
      >
        {formatInrPrecise(expectedNet)}
      </span>
    </motion.div>
  );
}

function AlternativeRow({ alt, show }: { alt: RejectedAlternativeOut; show: boolean }) {
  const tied = /^(\d+) candidates tied at this E\[net\]$/.exec(alt.description);
  return (
    <CandidateRow
      label={tied ? `${tied[1]} candidates (tied)` : alt.description}
      expectedNet={alt.expected_net}
      show={show}
    />
  );
}

function ClauseBadge({
  clause,
  rule,
  blocked,
}: {
  clause: ClauseRefOut;
  rule?: ComplianceRule;
  blocked?: boolean;
}) {
  return (
    <span
      title={rule?.text ?? clause.citation}
      className={`tabular-nums inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-medium ${
        blocked
          ? "bg-status-critical/15 text-status-critical-text"
          : "bg-status-good/15 text-status-good-text"
      }`}
    >
      <span className={`h-1.5 w-1.5 rounded-full ${blocked ? "bg-status-critical" : "bg-status-good"}`} />
      {clause.id}
    </span>
  );
}
