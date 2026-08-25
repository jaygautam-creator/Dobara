"""The audit trail. Append-only, never mutated — CLAUDE.md's "Audit everything"
non-negotiable, and docs/06-AGENT-SPEC.md's "## Audit trail": "Append-only. Never
mutated. One row per decision plus one row per executed action." (Execution rows are a
Phase 5 concern — the API/Razorpay integration layer that actually calls the rail; this
module owns the decision row and its rendering.)

`AuditTrail.append()` is the only mutator, and it only ever grows the record list —
there is no update/delete method, by construction, not by convention.

`render()` produces the exact block shape shown in docs/06-AGENT-SPEC.md's audit-trail
example (`SAW` / `THOUGHT` / `ALT` / `GATE` / `DID` / `WHY`), generated entirely from the
structured `Decision`/`DecisionContext` fields already computed by `agent/decide.py` —
no LLM, no re-derivation. The `WHY` line is a deterministic template over those same
numbers, not free-text generation; narrative polish belongs to `llm/` (Phase 6), which
`agent/` never imports.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from agent.actions import Abstain, EscalateToHuman, OfferDateChange, ScheduleDebit, Stop
from agent.context import Decision, DecisionContext


@dataclass(frozen=True)
class AuditRecord:
    ctx: DecisionContext
    decision: Decision


@dataclass
class AuditTrail:
    _records: list[AuditRecord] = field(default_factory=list)

    def append(self, ctx: DecisionContext, decision: Decision) -> AuditRecord:
        record = AuditRecord(ctx=ctx, decision=decision)
        self._records.append(record)
        return record

    def records(self) -> tuple[AuditRecord, ...]:
        """A copy-out view — mutating the returned tuple's referents does not, and
        cannot, alter what's already appended."""
        return tuple(self._records)


def _fmt_money(v: float) -> str:
    return f"Rs.{v:,.2f}"


def _fmt_pct_ci(point: float, lo: float, hi: float) -> str:
    return f"{point:.3f} [{lo:.3f}-{hi:.3f}]"


def _did_line(decision: Decision) -> str:
    action = decision.chosen
    if isinstance(action, ScheduleDebit):
        return (
            f"SEND_PRE_DEBIT_NOTICE({action.notice.t.isoformat()}, {action.notice.channel.value}, "
            f"{action.notice.template_id})\n"
            f"       SCHEDULE_DEBIT({action.t.isoformat()})   [proposal -> rzp test mode]"
        )
    if isinstance(action, OfferDateChange):
        return (
            f"OFFER_DATE_CHANGE({action.t.isoformat()}, {action.channel.value}, "
            f"day {action.new_preferred_day})"
        )
    if isinstance(action, Stop):
        return f"STOP({action.reason.value})"
    if isinstance(action, Abstain):
        return f"ABSTAIN({action.reason.value})   [no attempt -- not confident enough to act]"
    if isinstance(action, EscalateToHuman):
        return f"ESCALATE_TO_HUMAN({action.reason})"
    raise TypeError(f"no DID rendering for {type(action).__name__}")  # pragma: no cover


def _why_line(ctx: DecisionContext, decision: Decision) -> str:
    action = decision.chosen
    net = _fmt_money(decision.expected_net)
    if isinstance(action, ScheduleDebit):
        return (
            f'"Attempt {ctx.attempt_index} on {action.t.isoformat()} carries an expected net '
            f"recovery of {net}, the best of {len(decision.rejected_alternatives) + 1} candidates "
            f'considered, subject to every HARD compliance clause it satisfies below."'
        )
    if isinstance(action, OfferDateChange):
        return (
            f'"Offering a date change to day {action.new_preferred_day} was the '
            f'best-scoring candidate."'
        )
    if isinstance(action, Stop):
        return (
            f'"No candidate cleared a positive expected net recovery this cycle '
            f'({action.reason.value})."'
        )
    if isinstance(action, Abstain):
        return (
            f"\"The model's evidence for ({ctx.bank_id}, {ctx.method}) is not trusted enough "
            f"to act on ({action.reason.value}) — no attempt made this cycle. When in doubt, "
            f'the agent stops rather than guessing or falling back to an unvalidated default."'
        )
    if isinstance(action, EscalateToHuman):
        return f'"Handed to a human: {action.reason}."'
    raise TypeError(f"no WHY rendering for {type(action).__name__}")  # pragma: no cover


def render(record: AuditRecord) -> str:
    ctx, decision = record.ctx, record.decision
    rm = decision.rupee_math

    lines = [
        f"[{ctx.now.isoformat()}]  mandate {ctx.mandate_id}  cycle {ctx.cycle_index}  "
        f"attempt {ctx.attempt_index}",
        f"  SAW    {ctx.method} - {ctx.bank_id} - {_fmt_money(ctx.amount)} - "
        f"prev: {ctx.prev_error_source}/{ctx.prev_error_step}/{ctx.prev_error_reason}",
        f"         day_of_month {ctx.now.day} - attempt_index {ctx.attempt_index}",
        f"         notifications_this_cycle {ctx.notifications_sent_this_cycle} - "
        f"consecutive_failed_cycles {ctx.consecutive_failed_cycles} - "
        f"mandate_age {ctx.cycle_index - 1}",
        f"  THOUGHT P(success) = {rm.p_success:.3f}   P(revoke) = {rm.p_revoke:.3f}   "
        f"LTV_remaining = {_fmt_money(rm.ltv_remaining)}",
        f"          E[net] = {rm.p_success:.2f}x{rm.amount:.0f} - "
        f"{rm.p_revoke:.3f}x{rm.ltv_remaining:.0f} - {rm.cost:.2f} = "
        f"{_fmt_money(rm.expected_net)}  [{_fmt_money(decision.confidence_band[0])} - "
        f"{_fmt_money(decision.confidence_band[1])}]",
    ]

    if decision.rejected_alternatives:
        first = decision.rejected_alternatives[0]
        lines.append(
            f"  ALT     {first.description} -> E[net] {_fmt_money(first.expected_net)}   "
            f"({first.reason})"
        )
        for alt in decision.rejected_alternatives[1:]:
            lines.append(
                f"          {alt.description} -> E[net] {_fmt_money(alt.expected_net)}   "
                f"({alt.reason})"
            )
    else:
        lines.append(
            "  ALT     (none — this was a terminal precondition, nothing else was "
            "legally considerable)"
        )

    satisfied = " ".join(f"OK {c.id}" for c in decision.clauses_satisfied)
    blocked = " ".join(f"X {c.id}" for c in decision.clauses_blocked)
    lines.append(f"  GATE    {satisfied}")
    if blocked:
        lines.append(f"          {blocked}")

    lines.append(f"  DID     {_did_line(decision)}")
    lines.append(f"  WHY     {_why_line(ctx, decision)}")

    return "\n".join(lines)
