import type { ReactNode } from "react";
import type { AskWhyEntry, DecisionOut, RejectedAlternativeOut } from "@/lib/types";
import { formatInr, formatInrPrecise } from "@/lib/format";
import { Badge, Card } from "@/components/ui";
import { AskWhyBox } from "@/components/AskWhyBox";
import { DecisionEquation } from "@/components/audit/DecisionEquation";
import { didText, sawText, whyText } from "@/components/audit/renderAuditSections";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";

const TIED_PATTERN = /^(\d+) candidates tied at this E\[net\]$/;

/** Total candidates a decision actually considered: a tied row already summarizes N
 * candidates into one line, so the honest count sums those N's rather than counting
 * displayed rows (which would undercount) or list entries (ambiguous once rows collapse). */
export function totalCandidatesConsidered(alternatives: RejectedAlternativeOut[]): number {
  return alternatives.reduce((sum, alt) => {
    const m = TIED_PATTERN.exec(alt.description);
    return sum + (m ? Number(m[1]) : 1);
  }, 0);
}

/** Rejected alternatives as a comparison table -- docs/10-REDESIGN.md §4 `/audit/[id]`:
 * "what each scored, why it lost" -- rather than the previous bare list. A tied cluster
 * still collapses to one row (there's no channel/date field to key distinct ties on),
 * but now reads what/E[net]/why as three aligned columns instead of a truncated line. */
function RejectedAlternativesTable({ alternatives }: { alternatives: RejectedAlternativeOut[] }) {
  return (
    <div className="max-h-56 overflow-auto rounded-md border border-border">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Candidate</TableHead>
            <TableHead className="tabular-nums">E[net]</TableHead>
            <TableHead>Why it lost</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {alternatives.map((alt, i) => {
            const m = TIED_PATTERN.exec(alt.description);
            return (
              <TableRow key={i}>
                <TableCell className="max-w-[14rem] truncate">
                  {m ? `${m[1]} candidates (tied)` : alt.description}
                </TableCell>
                <TableCell className="tabular-nums whitespace-nowrap">
                  {formatInrPrecise(alt.expected_net)}
                </TableCell>
                <TableCell className="text-text-secondary">{alt.reason}</TableCell>
              </TableRow>
            );
          })}
        </TableBody>
      </Table>
    </div>
  );
}

const ACTION_LABEL: Record<string, string> = {
  schedule_debit: "Schedule debit",
  offer_date_change: "Offer date change",
  stop: "Stop",
  abstain: "Abstain",
  escalate_to_human: "Escalate to human",
};

export function AbstentionBanner({ decision }: { decision: DecisionOut }) {
  if (decision.chosen.action_type !== "abstain") return null;
  return (
    <div className="rounded-lg border border-status-warning/40 bg-status-warning/10 px-4 py-3 text-sm text-text-primary">
      <span className="font-semibold text-status-warning-text">Abstained.</span> Reason:{" "}
      <code className="text-text-secondary">{decision.chosen.abstain_reason}</code> — the
      agent declined to trust its own model here rather than guess.
    </div>
  );
}

/** A cell in the SAW/THOUGHT/ALT/GATE/DID/WHY grid -- one consistent label treatment so
 * the six sections read as one scannable structure rather than six differently-styled
 * paragraphs (docs/10-REDESIGN.md §4: "a labelled, scannable grid, not a stack of
 * paragraphs"). */
function GridCell({
  label,
  span,
  children,
}: {
  label: string;
  span?: boolean;
  children: ReactNode;
}) {
  return (
    <div className={`rounded-md border border-border bg-surface-0 p-3 ${span ? "sm:col-span-2" : ""}`}>
      <div className="mb-2 text-[10px] font-semibold uppercase tracking-wider text-text-muted">
        {label}
      </div>
      {children}
    </div>
  );
}

export function DecisionCard({ decision, bankId, method, askWhy }: {
  decision: DecisionOut;
  bankId?: string;
  method?: string;
  askWhy?: AskWhyEntry | null;
}) {
  const rm = decision.rupee_math;

  return (
    <Card className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <div className="tabular-nums text-xs uppercase tracking-wide text-text-muted">
            Mandate #{decision.mandate_id} · cycle {decision.cycle_index} · attempt{" "}
            {decision.attempt_index}
          </div>
          <div className="mt-0.5 text-lg font-semibold text-text-primary">
            {ACTION_LABEL[decision.chosen.action_type] ?? decision.chosen.action_type}
          </div>
        </div>
        <div className="flex items-center gap-2">
          {decision.requires_signoff && <Badge color="warning">needs sign-off</Badge>}
          <Badge>{bankId ?? decision.bank_id}</Badge>
          <Badge>{method ?? decision.method}</Badge>
        </div>
      </div>

      <AbstentionBanner decision={decision} />

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <GridCell label="SAW — context at decision time">
          <pre className="whitespace-pre-wrap font-mono text-[11px] leading-relaxed text-text-secondary">
            {sawText(decision)}
          </pre>
        </GridCell>

        <GridCell label="THOUGHT — the worked rupee maths">
          <DecisionEquation rm={rm} />
          <div className="tabular-nums mt-2 text-[11px] text-text-muted">
            95% confidence band: [{formatInr(decision.confidence_band[0])},{" "}
            {formatInr(decision.confidence_band[1])}]
          </div>
        </GridCell>

        <GridCell label={`ALT — rejected alternatives (${totalCandidatesConsidered(decision.rejected_alternatives)} considered)`} span>
          {decision.rejected_alternatives.length > 0 ? (
            <>
              <RejectedAlternativesTable alternatives={decision.rejected_alternatives.slice(0, 12)} />
              {decision.rejected_alternatives.length > 12 && (
                <div className="mt-1 text-xs text-text-muted">
                  +{totalCandidatesConsidered(decision.rejected_alternatives.slice(12))} more
                  candidates, in {decision.rejected_alternatives.length - 12} further rows not shown
                </div>
              )}
            </>
          ) : (
            <div className="text-xs text-text-muted">
              None — this was a terminal precondition; nothing else was legally considerable.
            </div>
          )}
        </GridCell>

        <GridCell label="GATE — compliance clauses">
          <div className="flex flex-wrap gap-1.5">
            {decision.clauses_satisfied.map((c) => (
              <span
                key={c.id}
                title={c.citation}
                className="tabular-nums inline-flex items-center gap-1 rounded-full bg-status-good/15 px-2 py-0.5 text-[11px] font-medium text-status-good-text"
              >
                <span className="h-1.5 w-1.5 rounded-full bg-status-good" />
                {c.id}
              </span>
            ))}
            {decision.clauses_blocked.map((c) => (
              <span
                key={c.id}
                title={c.citation}
                className="tabular-nums inline-flex items-center gap-1 rounded-full bg-status-critical/15 px-2 py-0.5 text-[11px] font-medium text-status-critical-text"
              >
                <span className="h-1.5 w-1.5 rounded-full bg-status-critical" />
                {c.id}
              </span>
            ))}
          </div>
        </GridCell>

        <GridCell label="DID — the action taken">
          <pre className="whitespace-pre-wrap font-mono text-[11px] leading-relaxed text-text-secondary">
            {didText(decision)}
          </pre>
        </GridCell>

        <GridCell label="WHY — the stated reason" span>
          <p className="text-sm italic leading-relaxed text-text-primary">
            {whyText(decision)}
          </p>
        </GridCell>
      </div>

      <AskWhyBox entry={askWhy ?? null} />
    </Card>
  );
}
