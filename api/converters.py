"""Converts `agent/` dataclasses into `api/schemas.py`'s Pydantic views. The only place
in `api/` that imports both — every route handler goes through here rather than building
a `schemas` model inline, so there is exactly one mapping to keep correct as either side
changes.
"""

from __future__ import annotations

from agent.actions import (
    Abstain,
    AbstentionReason,
    Action,
    Channel,
    EscalateToHuman,
    OfferDateChange,
    ScheduleDebit,
    SendPreDebitNotice,
    Stop,
)
from agent.audit import AuditRecord, RenderFields, render, render_fields
from agent.compliance import TEMPLATE_DATE_CHANGE, TEMPLATE_PDN
from agent.context import ClauseRef, Decision, RejectedAlternative, RupeeMath
from agent.stopping import StoppingReason
from api.schemas import (
    ActionOut,
    ClauseRefOut,
    CounterOut,
    DecisionOut,
    QueueItemOut,
    RejectedAlternativeOut,
    RupeeMathOut,
)
from eval.runner import MandateResult
from eval.world import World


def action_out(decision: Decision) -> ActionOut:
    action = decision.chosen
    if isinstance(action, ScheduleDebit):
        return ActionOut(
            action_type="schedule_debit",
            scheduled_at=action.t,
            channel=action.notice.channel.value,
            notice_at=action.notice.t,
        )
    if isinstance(action, OfferDateChange):
        return ActionOut(
            action_type="offer_date_change",
            scheduled_at=action.t,
            channel=action.channel.value,
            new_preferred_day=action.new_preferred_day,
        )
    if isinstance(action, Stop):
        return ActionOut(action_type="stop", stop_reason=action.reason.value)
    if isinstance(action, Abstain):
        return ActionOut(action_type="abstain", abstain_reason=action.reason.value)
    if isinstance(action, EscalateToHuman):
        return ActionOut(action_type="escalate_to_human", escalate_reason=action.reason)
    raise TypeError(f"no ActionOut mapping for {type(action).__name__}")  # pragma: no cover


def decision_out(record: AuditRecord) -> DecisionOut:
    ctx, decision = record.ctx, record.decision
    rm = decision.rupee_math
    return DecisionOut(
        mandate_id=ctx.mandate_id,
        cycle_index=ctx.cycle_index,
        attempt_index=ctx.attempt_index,
        bank_id=ctx.bank_id,
        method=ctx.method,
        amount=ctx.amount,
        now=ctx.now,
        chosen=action_out(decision),
        expected_net=decision.expected_net,
        confidence_band=decision.confidence_band,
        rejected_alternatives=[
            RejectedAlternativeOut(
                description=a.description, expected_net=a.expected_net, reason=a.reason
            )
            for a in decision.rejected_alternatives
        ],
        clauses_satisfied=[
            ClauseRefOut(id=c.id, citation=c.citation) for c in decision.clauses_satisfied
        ],
        clauses_blocked=[
            ClauseRefOut(id=c.id, citation=c.citation) for c in decision.clauses_blocked
        ],
        rupee_math=RupeeMathOut(
            p_success=rm.p_success,
            amount=rm.amount,
            p_revoke=rm.p_revoke,
            ltv_remaining=rm.ltv_remaining,
            cost=rm.cost,
            expected_net=rm.expected_net,
        ),
        model_versions=decision.model_versions,
        stopping_reason=decision.stopping_reason.value if decision.stopping_reason else None,
        requires_signoff=decision.requires_signoff,
        prev_error_source=ctx.prev_error_source,
        prev_error_step=ctx.prev_error_step,
        prev_error_reason=ctx.prev_error_reason,
        notifications_sent_this_cycle=ctx.notifications_sent_this_cycle,
        consecutive_failed_cycles=ctx.consecutive_failed_cycles,
        audit_text=render(record),
    )


def _action_from_out(a: ActionOut) -> Action:
    """Reverses `action_out()` -- reconstructs the `agent/actions.py` dataclass a
    `DecisionOut` was flattened from, for `render_from_decision_out()`. `notice`'s
    `template_id` (`ScheduleDebit`) and `OfferDateChange.template_id` aren't carried by
    `ActionOut` at all -- `agent/decide.py` only ever uses the two fixed module constants
    below (`TEMPLATE_PDN`/`TEMPLATE_DATE_CHANGE`), never a per-decision value, so
    reproducing them here is exact, not a guess. `afa_confirmed` similarly isn't in
    `ActionOut` -- unlike the template ids it *can* vary per decision, but nothing in the
    render path reads it (compliance-gate-only), so a fixed placeholder is harmless for
    this reconstruction specifically.
    """
    if a.action_type == "schedule_debit":
        assert a.scheduled_at is not None and a.channel is not None and a.notice_at is not None
        return ScheduleDebit(
            t=a.scheduled_at,
            notice=SendPreDebitNotice(
                t=a.notice_at, channel=Channel(a.channel), template_id=TEMPLATE_PDN
            ),
            afa_confirmed=False,
        )
    if a.action_type == "offer_date_change":
        assert (
            a.scheduled_at is not None and a.channel is not None and a.new_preferred_day is not None
        )
        return OfferDateChange(
            t=a.scheduled_at,
            channel=Channel(a.channel),
            template_id=TEMPLATE_DATE_CHANGE,
            new_preferred_day=a.new_preferred_day,
        )
    if a.action_type == "stop":
        assert a.stop_reason is not None
        return Stop(reason=StoppingReason(a.stop_reason))
    if a.action_type == "abstain":
        assert a.abstain_reason is not None
        return Abstain(reason=AbstentionReason(a.abstain_reason))
    if a.action_type == "escalate_to_human":
        assert a.escalate_reason is not None
        return EscalateToHuman(reason=a.escalate_reason)
    raise ValueError(
        f"no Action reconstruction for action_type={a.action_type!r}"
    )  # pragma: no cover


def render_from_decision_out(d: DecisionOut) -> str:
    """Regenerates `agent/audit.py`'s SAW/THOUGHT/ALT/GATE/DID/WHY block from an
    already-flattened `DecisionOut`, without a live `AuditRecord` -- the read path for
    `artifacts/demo_batch.json`'s fixture, which never serializes `audit_text` itself
    (per `docs/DECISIONS.md` [2026-08-27]). `decision_out()` above and this function
    must agree on every field `RenderFields` needs; `api/demo.py`'s round-trip test
    covers that they do.
    """
    rm = d.rupee_math
    fields = RenderFields(
        now=d.now,
        mandate_id=d.mandate_id,
        cycle_index=d.cycle_index,
        attempt_index=d.attempt_index,
        method=d.method,
        bank_id=d.bank_id,
        amount=d.amount,
        prev_error_source=d.prev_error_source,
        prev_error_step=d.prev_error_step,
        prev_error_reason=d.prev_error_reason,
        notifications_sent_this_cycle=d.notifications_sent_this_cycle,
        consecutive_failed_cycles=d.consecutive_failed_cycles,
        rupee_math=RupeeMath(
            p_success=rm.p_success,
            amount=rm.amount,
            p_revoke=rm.p_revoke,
            ltv_remaining=rm.ltv_remaining,
            cost=rm.cost,
            expected_net=rm.expected_net,
        ),
        confidence_band=d.confidence_band,
        rejected_alternatives=[
            RejectedAlternative(
                description=a.description, expected_net=a.expected_net, reason=a.reason
            )
            for a in d.rejected_alternatives
        ],
        clauses_satisfied=[ClauseRef(id=c.id, citation=c.citation) for c in d.clauses_satisfied],
        clauses_blocked=[ClauseRef(id=c.id, citation=c.citation) for c in d.clauses_blocked],
        chosen=_action_from_out(d.chosen),
    )
    return render_fields(fields)


def queue_items(records: list[AuditRecord], world: World) -> list[QueueItemOut]:
    """One `QueueItemOut` per mandate — its *first* audit record, representing the case
    as it entered the risk queue, per docs/08-FRONTEND-SPEC.md "Case queue, ranked by ₹
    at risk". Later cycles/attempts for the same mandate are still available in full via
    `/audit/{mandate_id}`; the queue itself is one row per case, not one per decision.
    """
    mandates_by_id = {m.mandate_id: m for m in world.mandates}
    seen: set[int] = set()
    items: list[QueueItemOut] = []
    for record in records:
        mandate_id = record.ctx.mandate_id
        if mandate_id in seen:
            continue
        seen.add(mandate_id)
        spec = mandates_by_id[mandate_id]
        items.append(
            QueueItemOut(
                mandate_id=mandate_id,
                bank_id=spec.customer.bank_id,
                method=record.ctx.method,
                merchant_category=spec.merchant_category,
                amount=spec.amount,
                is_cold_start=spec.is_cold_start,
                regime_shift_bank=spec.regime_shift_bank,
                decision=decision_out(record),
            )
        )
    items.sort(key=lambda item: item.amount, reverse=True)
    return items


def compute_counters(
    dobara_results: list[MandateResult], aggressive_8x_results: list[MandateResult]
) -> CounterOut:
    """Two `MandateResult` lists (one per arm, same population) -> `CounterOut`.
    Header-tile numbers, per docs/08-FRONTEND-SPEC.md: "₹ at risk → ₹ recovered → ₹ net
    LTV → notifications sent → revocations avoided → attempts *not* made" plus the
    comparison-toggle's `aggressive_8x` figures on the same population. Takes the two
    result lists directly rather than `api/demo.py::DemoBatch` so this module never needs
    to import `api.demo` (which itself imports this module) -- keeps the dependency
    one-directional."""
    dobara = dobara_results
    agg = aggressive_8x_results
    return CounterOut(
        n_mandates=len(dobara),
        amount_at_risk_inr=sum(r.amount for r in dobara),
        gross_recovered_inr=sum(r.gross_recovered_inr for r in dobara),
        net_ltv_inr=sum(r.net_ltv_inr for r in dobara),
        notifications_sent=sum(r.n_notifications for r in dobara),
        revocations=sum(1 for r in dobara if r.revoked),
        attempts_not_made=sum(r.n_abstentions for r in dobara),
        comparison_aggressive_8x_gross_recovered_inr=sum(r.gross_recovered_inr for r in agg),
        comparison_aggressive_8x_net_ltv_inr=sum(r.net_ltv_inr for r in agg),
        comparison_aggressive_8x_revocations=sum(1 for r in agg if r.revoked),
    )
