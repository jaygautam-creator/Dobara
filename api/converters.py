"""Converts `agent/` dataclasses into `api/schemas.py`'s Pydantic views. The only place
in `api/` that imports both — every route handler goes through here rather than building
a `schemas` model inline, so there is exactly one mapping to keep correct as either side
changes.
"""

from __future__ import annotations

from agent.actions import Abstain, EscalateToHuman, OfferDateChange, ScheduleDebit, Stop
from agent.audit import AuditRecord, render
from agent.context import Decision
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
        audit_text=render(record),
    )


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
