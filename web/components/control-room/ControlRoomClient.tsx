"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useRef, useState, type KeyboardEvent as ReactKeyboardEvent } from "react";
import { motion, useMotionValue, useSpring, useTransform } from "motion/react";
import type {
  AskWhyEntry,
  ComplianceRule,
  CounterOut,
  DecisionOut,
  QueueRow,
} from "@/lib/types";
import { formatInr, formatNumber } from "@/lib/format";
import { useStaticRender } from "@/lib/motion";
import { Badge, Card, StatTile } from "@/components/ui";
import { DecisionCard, totalCandidatesConsidered } from "@/components/DecisionCard";
import {
  Command,
  CommandDialog,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";

const ACTION_BADGE_COLOR: Record<string, "good" | "warning" | "critical" | "neutral"> = {
  schedule_debit: "good",
  offer_date_change: "neutral",
  stop: "neutral",
  abstain: "warning",
  escalate_to_human: "critical",
};

const RESTRAINED_ACTIONS = new Set(["stop", "abstain", "escalate_to_human"]);

const REVEAL_INTERVAL_MS = 45;

/** Ticks a number from its last rendered value to `value` -- docs/10-REDESIGN.md §4:
 * "the aggressive_8x comparison toggle currently swaps numbers silently. Animate the
 * delta." A static render (screenshot pass, prefers-reduced-motion) jumps straight to
 * the target instead of tweening -- §5's determinism rule applies to every animation
 * this route adds, not just the ones inherited from Session C. */
function AnimatedNumber({
  value,
  format = (v) => formatNumber(Math.round(v)),
}: {
  value: number;
  format?: (v: number) => string;
}) {
  const isStatic = useStaticRender();
  const motionValue = useMotionValue(value);
  const spring = useSpring(motionValue, { stiffness: 140, damping: 24, mass: 0.6 });
  const display = useTransform(spring, format);

  useEffect(() => {
    if (isStatic) {
      motionValue.jump(value);
    } else {
      motionValue.set(value);
    }
  }, [value, isStatic, motionValue]);

  return <motion.span>{display}</motion.span>;
}

/** `+2,140 notifications` / `-18 revocations` -- the honest reading of the toggle: what
 * changes, and whether that change is good or bad news, in status colour rather than
 * left for the reader to infer from two silently-swapped numbers. */
function DeltaAnnotation({
  from,
  to,
  goodDirection,
  unit,
}: {
  from: number;
  to: number;
  goodDirection: "up" | "down";
  unit: string;
}) {
  const diff = to - from;
  if (diff === 0) return null;
  const rose = diff > 0;
  const isGood = goodDirection === "up" ? rose : !rose;
  return (
    <span
      className={`tabular-nums ml-1.5 text-xs font-medium ${
        isGood ? "text-status-good-text" : "text-status-critical-text"
      }`}
    >
      {rose ? "+" : "−"}
      {formatNumber(Math.abs(diff))} {unit}
    </span>
  );
}

/** docs/10-REDESIGN.md §4: "add the compliance gate panel to the active case: candidate
 * set generated, which HARD rules eliminated what, what survived to be scored." The
 * per-candidate elimination trace isn't serialized (agent/decide.py filters candidates
 * against every HARD rule before scoring, but only the chosen action's own
 * clauses_satisfied/clauses_blocked survive into DecisionOut) -- so this panel reports
 * exactly what the data supports: how many candidates were legal enough to be scored at
 * all (from rejected_alternatives, the same count DecisionCard already shows), and which
 * named clauses the winning action itself satisfies or is flagged against. It does not
 * invent a per-rule elimination count nothing in artifacts/demo_batch.json contains. */
function CaseComplianceGate({
  decision,
  rules,
}: {
  decision: DecisionOut;
  rules: ComplianceRule[];
}) {
  const ruleById = useMemo(() => new Map(rules.map((r) => [r.id, r])), [rules]);
  const nCandidates = totalCandidatesConsidered(decision.rejected_alternatives) + 1;

  return (
    <Card className="space-y-3">
      <div className="text-xs font-semibold uppercase tracking-wide text-text-muted">
        Compliance gate — mandate #{decision.mandate_id}
      </div>
      <div className="grid grid-cols-1 gap-3 rounded-md bg-surface-0 p-3 text-center sm:grid-cols-3">
        <div>
          <div className="tabular-nums text-lg font-semibold text-text-primary">
            {nCandidates}
          </div>
          <div className="text-[11px] text-text-muted">candidates legal enough to score</div>
        </div>
        <div>
          <div className="tabular-nums text-lg font-semibold text-status-critical-text">
            {decision.clauses_blocked.length}
          </div>
          <div className="text-[11px] text-text-muted">clauses flagged on the winner</div>
        </div>
        <div>
          <div className="tabular-nums text-lg font-semibold text-status-good-text">
            {decision.clauses_satisfied.length}
          </div>
          <div className="text-[11px] text-text-muted">clauses satisfied by the winner</div>
        </div>
      </div>
      {decision.clauses_blocked.length > 0 ? (
        <ul className="space-y-1.5">
          {decision.clauses_blocked.map((c) => {
            const rule = ruleById.get(c.id);
            return (
              <li
                key={c.id}
                className="rounded-md bg-status-critical/10 px-2.5 py-1.5 text-xs leading-relaxed text-text-secondary"
              >
                <span className="tabular-nums font-semibold text-status-critical-text">{c.id}</span>{" "}
                {rule?.text ?? c.citation}
              </li>
            );
          })}
        </ul>
      ) : (
        <p className="text-xs leading-relaxed text-text-secondary">
          No clause is flagged against this case&apos;s chosen action — every candidate this
          route rejected lost on expected value, not compliance. Every HARD rule a
          candidate could trip disqualifies it before scoring even starts (see{" "}
          <Link href="/architecture" className="underline decoration-dotted underline-offset-2">
            /architecture
          </Link>{" "}
          for the full gate).
        </p>
      )}
    </Card>
  );
}

export function ControlRoomClient({
  rows,
  counters,
  topCaseDecision,
  topCaseAskWhy,
  approvals,
  complianceRules,
}: {
  rows: QueueRow[];
  counters: CounterOut;
  topCaseDecision: DecisionOut;
  topCaseAskWhy: AskWhyEntry | null;
  approvals: DecisionOut[];
  complianceRules: ComplianceRule[];
}) {
  const router = useRouter();
  const isStatic = useStaticRender();
  const [liveRevealed, setLiveRevealed] = useState(0);
  // A static render (screenshot pass, prefers-reduced-motion) gets the completed batch
  // immediately, same rule as Demonstration.tsx's `step` -- never derived via setState in
  // an effect (that cascades a render); `isStatic` picks the value directly.
  const revealed = isStatic ? rows.length : liveRevealed;
  const [comparing, setComparing] = useState(false);
  const [selectedId, setSelectedId] = useState<number>(topCaseDecision.mandate_id);
  const [restrainedOnly, setRestrainedOnly] = useState(false);
  const [paletteOpen, setPaletteOpen] = useState(false);
  const rowRefs = useRef<Map<number, HTMLTableRowElement>>(new Map());

  const restrainedCount = useMemo(
    () => rows.filter((r) => RESTRAINED_ACTIONS.has(r.terminal_action_type)).length,
    [rows],
  );

  useEffect(() => {
    if (isStatic || liveRevealed >= rows.length) return;
    const t = setTimeout(() => setLiveRevealed((n) => n + 1), REVEAL_INTERVAL_MS);
    return () => clearTimeout(t);
  }, [liveRevealed, rows.length, isStatic]);

  const visibleRows = rows
    .slice(0, revealed)
    .filter((r) => !restrainedOnly || RESTRAINED_ACTIONS.has(r.terminal_action_type));
  const streaming = revealed < rows.length;
  const progress = revealed / Math.max(rows.length, 1);

  const selectedRow = useMemo(
    () => rows.find((r) => r.mandate_id === selectedId) ?? rows[0],
    [rows, selectedId],
  );
  const activeDecision = selectedId === topCaseDecision.mandate_id ? topCaseDecision : null;

  // ⌘K / Ctrl+K opens the mandate jump-to palette from anywhere on the page, standard
  // command-palette convention -- docs/10-REDESIGN.md §4: "`command` palette to jump to
  // a mandate by ID".
  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === "k" && (e.metaKey || e.ctrlKey)) {
        e.preventDefault();
        setPaletteOpen((o) => !o);
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, []);

  function jumpTo(mandateId: number) {
    setSelectedId(mandateId);
    setPaletteOpen(false);
    rowRefs.current.get(mandateId)?.scrollIntoView({ block: "nearest" });
  }

  // ↑/↓ move the active-case selection, Enter opens the full audit page -- §4's
  // "keyboard navigable (↑/↓ to move, Enter to open)". Scoped to the queue's own
  // container so arrow keys don't hijack scrolling elsewhere on the page.
  function onQueueKeyDown(e: ReactKeyboardEvent<HTMLDivElement>) {
    if (e.key !== "ArrowUp" && e.key !== "ArrowDown" && e.key !== "Enter") return;
    e.preventDefault();
    const idx = visibleRows.findIndex((r) => r.mandate_id === selectedId);
    if (e.key === "Enter") {
      if (selectedRow) router.push(`/audit/${selectedRow.mandate_id}`);
      return;
    }
    const nextIdx =
      e.key === "ArrowDown"
        ? Math.min(idx < 0 ? 0 : idx + 1, visibleRows.length - 1)
        : Math.max(idx < 0 ? 0 : idx - 1, 0);
    const next = visibleRows[nextIdx];
    if (next) {
      setSelectedId(next.mandate_id);
      rowRefs.current.get(next.mandate_id)?.scrollIntoView({ block: "nearest" });
    }
  }

  const netLtv = comparing ? counters.comparison_aggressive_8x_net_ltv_inr : counters.net_ltv_inr;
  const revocations = comparing
    ? counters.comparison_aggressive_8x_revocations
    : counters.revocations;

  return (
    <div
      className="space-y-8"
      // §5: "never make a judge wait." Anywhere on the streaming reveal completes it
      // instantly -- the reveal itself is a `motion`-driven fade per row (LaneColumn's
      // pattern from Demonstration.tsx), not a hard pop.
      onClick={() => {
        if (streaming) setLiveRevealed(rows.length);
      }}
    >
      <CommandDialog open={paletteOpen} onOpenChange={setPaletteOpen}>
        <Command>
          <CommandInput placeholder="Jump to a mandate by ID…" />
          <CommandList>
            <CommandEmpty>No mandate matches.</CommandEmpty>
            <CommandGroup heading="Mandates">
              {rows.map((r) => (
                <CommandItem
                  key={r.mandate_id}
                  value={String(r.mandate_id)}
                  onSelect={() => jumpTo(r.mandate_id)}
                >
                  <span className="tabular-nums">#{r.mandate_id}</span>
                  <span className="ml-2 text-text-muted">
                    {r.bank_id} · {r.merchant_category} · {formatInr(r.amount)}
                  </span>
                </CommandItem>
              ))}
            </CommandGroup>
          </CommandList>
        </Command>
      </CommandDialog>

      <div>
        <div className="mb-3 flex items-center justify-between">
          <div className="text-xs text-text-muted">
            {streaming
              ? `Streaming batch — ${revealed}/${rows.length} cases (click anywhere to skip)`
              : `Batch complete — ${rows.length} cases`}
          </div>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                setPaletteOpen(true);
              }}
              className="rounded-md border border-border bg-surface-1 px-3 py-1.5 text-xs font-medium text-text-secondary transition-colors hover:bg-surface-2"
            >
              Jump to mandate <span className="ml-1 text-text-muted">⌘K</span>
            </button>
            <button
              onClick={(e) => {
                e.stopPropagation();
                setComparing((c) => !c);
              }}
              className={`rounded-md border px-3 py-1.5 text-xs font-semibold transition-colors ${
                comparing
                  ? "border-arm-aggressive-8x bg-arm-aggressive-8x/15 text-arm-aggressive-8x"
                  : "border-border bg-surface-1 text-text-secondary hover:bg-surface-2"
              }`}
            >
              {comparing
                ? "Showing: aggressive_8x would have..."
                : "Show what aggressive_8x would have done"}
            </button>
          </div>
        </div>
        <div className="h-1 w-full overflow-hidden rounded-full bg-surface-2">
          <motion.div
            className="h-full bg-arm-dobara"
            animate={{ width: `${progress * 100}%` }}
            transition={isStatic ? { duration: 0 } : { duration: 0.25, ease: [0.2, 0, 0, 1] }}
          />
        </div>
      </div>

      {/* Hero/compact hierarchy -- docs/10-REDESIGN.md §4: net LTV is the one `hero`
          tile on the page; everything else is `compact`. */}
      <div className="grid gap-3 lg:grid-cols-[1.4fr_1fr]">
        <StatTile
          label="₹ net LTV"
          tone="good"
          size="hero"
          value={formatInr(netLtv, { compact: true })}
          source={
            comparing
              ? "counters.comparison_aggressive_8x_net_ltv_inr -- live fixture total, not a statistical estimate"
              : "counters.net_ltv_inr -- live fixture total, not a statistical estimate"
          }
          noCi="a running total over this fixed demo batch, not a bootstrapped quantity"
        />
        <AttemptsNotMadeFeature value={counters.attempts_not_made} />
      </div>

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <StatTile
          label="₹ at risk (this cycle)"
          size="compact"
          value={formatInr(counters.amount_at_risk_inr, { compact: true })}
          source="sum of each mandate's due amount for its current billing cycle only"
          noCi="a live fixture total, not a statistical estimate"
        />
        <StatTile
          label="₹ recovered (gross, all cycles)"
          size="compact"
          value={formatInr(
            comparing ? counters.comparison_aggressive_8x_gross_recovered_inr : counters.gross_recovered_inr,
            { compact: true },
          )}
          source="cumulative across every cycle simulated per mandate -- not comparable to at-risk"
          noCi="a live fixture total, not a statistical estimate"
        />
        <StatTile
          label="Notifications sent"
          size="compact"
          value={formatNumber(counters.notifications_sent)}
          source="counters.notifications_sent -- live fixture count"
          noCi="a live fixture count, not a statistical estimate"
        />
        <div className="rounded-lg border border-border bg-surface-1 p-3">
          <div className="text-xs font-medium uppercase tracking-wider text-text-muted">
            Revocations
          </div>
          <div
            className={`mt-1.5 font-mono tabular-nums text-step-2 font-semibold ${
              comparing ? "text-status-critical-text" : "text-status-good-text"
            }`}
          >
            <AnimatedNumber value={revocations} />
            {comparing && (
              <DeltaAnnotation
                from={counters.revocations}
                to={counters.comparison_aggressive_8x_revocations}
                goodDirection="down"
                unit="revocations"
              />
            )}
          </div>
          <div className="mt-1 text-xs italic text-text-muted">
            no CI — a live fixture count, not a statistical estimate
          </div>
          <div className="mt-1 text-[11px] break-words text-text-muted">
            counters.revocations / comparison_aggressive_8x_revocations
          </div>
        </div>
      </div>

      {approvals.length > 0 && (
        <Card>
          <h3 className="mb-2 text-sm font-semibold text-text-primary">
            Approval queue ({approvals.length})
          </h3>
          <p className="text-xs text-text-secondary">
            Decisions above the human sign-off threshold — nothing above it runs
            autonomously.
          </p>
        </Card>
      )}

      <div className="grid gap-6 lg:grid-cols-[1fr_1.1fr]">
        <div onKeyDown={onQueueKeyDown} tabIndex={0} className="outline-none focus-visible:ring-2 focus-visible:ring-arm-dobara/40 rounded-lg">
          <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
            <h3 className="text-sm font-semibold text-text-primary">
              Case queue, ranked by ₹ at risk
            </h3>
            <div className="flex items-center rounded-md border border-border bg-surface-1 p-0.5 text-xs">
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  setRestrainedOnly(false);
                }}
                className={`rounded px-2 py-1 font-medium transition-colors ${
                  !restrainedOnly
                    ? "bg-surface-2 text-text-primary"
                    : "text-text-secondary hover:text-text-primary"
                }`}
              >
                All {rows.length}
              </button>
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  setRestrainedOnly(true);
                }}
                className={`rounded px-2 py-1 font-medium transition-colors ${
                  restrainedOnly
                    ? "bg-arm-dobara/15 text-arm-dobara-text"
                    : "text-text-secondary hover:text-text-primary"
                }`}
              >
                Ended in stop or abstain ({restrainedCount})
              </button>
            </div>
          </div>
          <ScrollArea className="h-[720px] w-full rounded-lg border border-border">
            <Table>
              <TableHeader className="sticky top-0 z-10 bg-surface-1">
                <TableRow className="hover:bg-transparent">
                  <TableHead>Mandate</TableHead>
                  <TableHead>Action</TableHead>
                  <TableHead className="text-right">Amount</TableHead>
                  <TableHead className="text-right">Audit</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {visibleRows.map((row, i) => (
                  <motion.tr
                    key={row.mandate_id}
                    ref={(el) => {
                      if (el) rowRefs.current.set(row.mandate_id, el);
                      else rowRefs.current.delete(row.mandate_id);
                    }}
                    initial={isStatic ? false : { opacity: 0, y: 4 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={
                      isStatic
                        ? { duration: 0 }
                        : { duration: 0.18, ease: [0.2, 0, 0, 1], delay: Math.min(i, 8) * 0.01 }
                    }
                    onClick={(e) => {
                      e.stopPropagation();
                      setSelectedId(row.mandate_id);
                    }}
                    aria-selected={selectedRow?.mandate_id === row.mandate_id}
                    className={`cursor-pointer border-b border-border last:border-0 transition-colors hover:bg-surface-2 ${
                      selectedRow?.mandate_id === row.mandate_id ? "bg-arm-dobara/[0.08]" : "bg-surface-1"
                    }`}
                  >
                    <TableCell className="px-3 py-2">
                      <div className="font-medium text-text-primary">#{row.mandate_id}</div>
                      <div className="text-[11px] text-text-muted">
                        {row.bank_id} · {row.merchant_category}
                      </div>
                    </TableCell>
                    <TableCell className="px-3 py-2">
                      <Badge color={ACTION_BADGE_COLOR[row.action_type] ?? "neutral"}>
                        {row.action_type}
                      </Badge>
                      {row.terminal_action_type !== row.action_type &&
                        RESTRAINED_ACTIONS.has(row.terminal_action_type) && (
                          <span className="ml-1.5 inline-block">
                            <Badge color={ACTION_BADGE_COLOR[row.terminal_action_type] ?? "neutral"}>
                              → {row.terminal_action_type}
                            </Badge>
                          </span>
                        )}
                      {row.regime_shift_bank && (
                        <span className="ml-1.5 text-[10px] text-status-warning-text">shift</span>
                      )}
                    </TableCell>
                    <TableCell className="tabular-nums px-3 py-2 text-right font-medium text-text-primary">
                      {formatInr(row.amount)}
                    </TableCell>
                    <TableCell className="whitespace-normal px-3 py-2 text-right">
                      <Link
                        href={`/audit/${row.mandate_id}`}
                        onClick={(e) => e.stopPropagation()}
                        className="text-[11px] text-arm-dobara-text hover:underline"
                      >
                        full audit →
                      </Link>
                    </TableCell>
                  </motion.tr>
                ))}
              </TableBody>
            </Table>
          </ScrollArea>
        </div>

        <div className="space-y-4 lg:sticky lg:top-20 lg:self-start" onClick={(e) => e.stopPropagation()}>
          <h3 className="text-sm font-semibold text-text-primary">Active case</h3>
          {activeDecision ? (
            <>
              <DecisionCard decision={activeDecision} askWhy={topCaseAskWhy} />
              <CaseComplianceGate decision={activeDecision} rules={complianceRules} />
            </>
          ) : (
            <Card>
              <p className="text-sm text-text-secondary">
                Full decision detail for mandate #{selectedId} is on its own page (kept out
                of the Control Room bundle — see <code>/audit/{selectedId}</code>).
              </p>
              <Link
                href={`/audit/${selectedId}`}
                className="mt-3 inline-block text-sm font-medium text-arm-dobara-text hover:underline"
              >
                Open full audit →
              </Link>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}

/** §4: "'Attempts not made' is the thesis counter -- give it the `feature` treatment and
 * a short caption saying why a *non*-action is the headline." `feature` is rationed to
 * one per page (§3.2); this is the one on `/control-room`. */
function AttemptsNotMadeFeature({ value }: { value: number }) {
  return (
    <Card variant="feature" className="flex flex-col justify-between gap-2">
      <div>
        <div className="text-xs font-medium uppercase tracking-wider text-text-muted">
          Attempts not made
        </div>
        <div className="mt-1.5 font-mono tabular-nums text-step-4 font-semibold text-arm-dobara-text">
          <AnimatedNumber value={value} />
        </div>
      </div>
      <p className="text-xs leading-relaxed text-text-secondary">
        The headline metric on this page is a <strong>non</strong>-action: every count here
        is a retry dobara&apos;s own model priced as a losing bet and skipped — one fewer
        mandatory pre-debit notification, one fewer mandate put at risk of revocation. A
        recovery agent scored only on money moved would never surface this number;
        restraint is the product.
      </p>
      <div className="text-[11px] text-text-muted">
        counters.attempts_not_made — live fixture count, not a statistical estimate
      </div>
    </Card>
  );
}
