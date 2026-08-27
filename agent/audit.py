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

**`audit_text` is a rendering, not stored data — deliberately.** `RenderFields` is the
one small set of scalars the render actually needs; `render()` extracts it from an
`AuditRecord`, but nothing here requires a live `AuditRecord` — `api/converters.py`'s
`render_from_decision_out()` builds the identical `RenderFields` from the API's
already-flattened `DecisionOut` and calls the same `render_fields()`. This is why
`artifacts/demo_batch.json` (per `docs/DECISIONS.md` [2026-08-27]) never serializes the
11.7 KB rendered string per decision: everything `render_fields()` needs is already in the
committed structured fields, so the text is regenerated at read time instead of stored
1,296 times.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from agent.actions import Abstain, Action, EscalateToHuman, OfferDateChange, ScheduleDebit, Stop
from agent.context import ClauseRef, Decision, DecisionContext, RejectedAlternative, RupeeMath


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


@dataclass(frozen=True)
class RenderFields:
    """Exactly what `render_fields()` needs, and nothing it doesn't — the shared shape between
    a live `AuditRecord` (`_fields_from_record`) and an API `DecisionOut`
    (`api/converters.py::render_from_decision_out`). If `render_fields()` ever needs a new
    field, add it here first so both producers are forced to supply it.
    """

    now: datetime
    mandate_id: int
    cycle_index: int
    attempt_index: int
    method: str
    bank_id: str
    amount: float
    prev_error_source: str | None
    prev_error_step: str | None
    prev_error_reason: str | None
    notifications_sent_this_cycle: int
    consecutive_failed_cycles: int
    rupee_math: RupeeMath
    confidence_band: tuple[float, float]
    rejected_alternatives: list[RejectedAlternative]
    clauses_satisfied: list[ClauseRef]
    clauses_blocked: list[ClauseRef]
    chosen: Action


def _fields_from_record(record: AuditRecord) -> RenderFields:
    ctx, decision = record.ctx, record.decision
    return RenderFields(
        now=ctx.now,
        mandate_id=ctx.mandate_id,
        cycle_index=ctx.cycle_index,
        attempt_index=ctx.attempt_index,
        method=ctx.method,
        bank_id=ctx.bank_id,
        amount=ctx.amount,
        prev_error_source=ctx.prev_error_source,
        prev_error_step=ctx.prev_error_step,
        prev_error_reason=ctx.prev_error_reason,
        notifications_sent_this_cycle=ctx.notifications_sent_this_cycle,
        consecutive_failed_cycles=ctx.consecutive_failed_cycles,
        rupee_math=decision.rupee_math,
        confidence_band=decision.confidence_band,
        rejected_alternatives=decision.rejected_alternatives,
        clauses_satisfied=decision.clauses_satisfied,
        clauses_blocked=decision.clauses_blocked,
        chosen=decision.chosen,
    )


def _fmt_money(v: float) -> str:
    return f"Rs.{v:,.2f}"


def _did_line(action: Action) -> str:
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


def _why_line(fields: RenderFields) -> str:
    action = fields.chosen
    net = _fmt_money(fields.rupee_math.expected_net)
    if isinstance(action, ScheduleDebit):
        return (
            f'"Attempt {fields.attempt_index} on {action.t.isoformat()} carries an expected net '
            f"recovery of {net}, the best of {len(fields.rejected_alternatives) + 1} candidates "
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
            f"\"The model's evidence for ({fields.bank_id}, {fields.method}) is not trusted "
            f"enough to act on ({action.reason.value}) — no attempt made this cycle. When in "
            f"doubt, the agent stops rather than guessing or falling back to an unvalidated "
            f'default."'
        )
    if isinstance(action, EscalateToHuman):
        return f'"Handed to a human: {action.reason}."'
    raise TypeError(f"no WHY rendering for {type(action).__name__}")  # pragma: no cover


def render_fields(fields: RenderFields) -> str:
    rm = fields.rupee_math

    lines = [
        f"[{fields.now.isoformat()}]  mandate {fields.mandate_id}  cycle {fields.cycle_index}  "
        f"attempt {fields.attempt_index}",
        f"  SAW    {fields.method} - {fields.bank_id} - {_fmt_money(fields.amount)} - "
        f"prev: {fields.prev_error_source}/{fields.prev_error_step}/{fields.prev_error_reason}",
        f"         day_of_month {fields.now.day} - attempt_index {fields.attempt_index}",
        f"         notifications_this_cycle {fields.notifications_sent_this_cycle} - "
        f"consecutive_failed_cycles {fields.consecutive_failed_cycles} - "
        f"mandate_age {fields.cycle_index - 1}",
        f"  THOUGHT P(success) = {rm.p_success:.3f}   P(revoke) = {rm.p_revoke:.3f}   "
        f"LTV_remaining = {_fmt_money(rm.ltv_remaining)}",
        f"          E[net] = {rm.p_success:.2f}x{rm.amount:.0f} - "
        f"{rm.p_revoke:.3f}x{rm.ltv_remaining:.0f} - {rm.cost:.2f} = "
        f"{_fmt_money(rm.expected_net)}  [{_fmt_money(fields.confidence_band[0])} - "
        f"{_fmt_money(fields.confidence_band[1])}]",
    ]

    if fields.rejected_alternatives:
        first = fields.rejected_alternatives[0]
        lines.append(
            f"  ALT     {first.description} -> E[net] {_fmt_money(first.expected_net)}   "
            f"({first.reason})"
        )
        for alt in fields.rejected_alternatives[1:]:
            lines.append(
                f"          {alt.description} -> E[net] {_fmt_money(alt.expected_net)}   "
                f"({alt.reason})"
            )
    else:
        lines.append(
            "  ALT     (none — this was a terminal precondition, nothing else was "
            "legally considerable)"
        )

    satisfied = " ".join(f"OK {c.id}" for c in fields.clauses_satisfied)
    blocked = " ".join(f"X {c.id}" for c in fields.clauses_blocked)
    lines.append(f"  GATE    {satisfied}")
    if blocked:
        lines.append(f"          {blocked}")

    lines.append(f"  DID     {_did_line(fields.chosen)}")
    lines.append(f"  WHY     {_why_line(fields)}")

    return "\n".join(lines)


def render(record: AuditRecord) -> str:
    return render_fields(_fields_from_record(record))
