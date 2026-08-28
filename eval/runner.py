"""Drives each of the 5 arms (`eval/arms.py::Arm`) cycle-by-cycle over a shared
`eval.world.World`, producing one `MandateResult` per mandate per arm. Every stochastic
draw (attempt outcome, revocation roll, date-change response) goes through
`eval.rng.event_rng` for cross-arm fairness — see that module's docstring for why a
shared sequential stream would be unfair here (docs/07-EVAL-SPEC.md: "identical seeds,
identical simulator state").

`do_nothing`/`razorpay_default`/`aggressive_8x` are fixed-cadence arms (`eval/arms.py`).
`dobara` calls `agent.decide()` live against the already-trained Phase 2/3 model bundle
(`agent/models.py::ModelBundle`, loaded once by the caller from the training DB/artifacts
and reused read-only here — models are trained once and evaluated against fresh held-out
populations, never retrained per eval seed). `oracle` is the one arm allowed to look at
`sim.latent.CustomerLatent` directly — the ceiling reference is explicitly permitted to
cheat (docs/07-EVAL-SPEC.md: "Perfect foresight over latent state") — it picks its
attempt day from the customer's deterministic expected-balance curve (no rng: this is
knowledge, not a draw) and avoids any bank day it independently knows is a dated outage,
**and it also decides whether to retry at all using the TRUE generative probabilities**
(`_true_p_success`, an exact closed-form expectation over `sim.latent.balance_available`'s
noise, plus the real `sim.engine.revocation_hazard`) rather than a trained model's
estimates — stopping a cycle the instant true `E[net] <= 0`, exactly the discipline
`agent/decide.py` approximates for `dobara`. It still faces the same stochastic bank-side
draw every other arm faces for whichever attempts it does make — perfect knowledge of the
generating probabilities is not the same as knowing a specific coin flip's result in
advance, and this arm deliberately does not peek at that. No other arm in this module
imports `sim.latent`.

**2026-08-25 fix:** oracle previously used foresight only for day-selection, then still
blindly retried up to `retry_policy.max_attempts_default_policy` times per cycle on a
fixed cadence with no stopping logic — identical retry structure to `razorpay_default`.
That let it accumulate the same notification-driven revocation exposure as
`razorpay_default` (even slightly more, since day-selection alone barely reduces the
technical-decline half of `sim.engine.attempt_outcome`'s failure probability) while
gaining almost nothing from the smarter day choice, so it underperformed both
`razorpay_default` and `do_nothing` on net LTV — a logical impossibility for an arm with
strictly more information than every other arm. See `docs/DECISIONS.md` [2026-08-25]
"oracle arm: fixed missing stopping logic".

**Net LTV accounting is the harness's own bookkeeping, identical across all 5 arms** —
not a per-decision model estimate. When a revocation actually fires (via the TRUE
generative `sim.engine.revocation_hazard`, exactly the mechanism that produced Phase 1/2's
training data — never `models.hazard`'s prediction, which only steers `dobara`'s own
choices), the LTV lost is priced with `models.ltv.ltv_remaining` against one shared
`LifeTable` built once from the training DB, so every arm's "net LTV" is comparable on
the same yardstick.

**Documented simplifications**, not modelled by this harness (none of them existed in
Phase 1's `sim.engine` either, so no arm is disadvantaged relative to another):
`total_contacts_30d` is approximated as the mandate's cumulative failure-notification
count rather than a true rolling 30-day window; `has_customer_engaged_with_notice` is
always `False`; there is no customer opt-out mechanic, so `customer_opted_out` is always
`False` for every arm.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta

import numpy as np

from agent.actions import Abstain, EscalateToHuman, OfferDateChange, ScheduleDebit, Stop
from agent.audit import AuditTrail
from agent.context import DecisionContext
from agent.decide import decide
from agent.models import ModelBundle
from agent.policy import PolicyConfig
from eval.arms import (
    DO_NOTHING_CADENCE,
    Arm,
    Cadence,
    aggressive_8x_cadence,
    razorpay_default_cadence,
)
from eval.rng import event_rng
from eval.world import MandateSpec, World
from models.ltv import LifeTable, ltv_remaining
from sim.engine import attempt_outcome, revocation_hazard
from sim.latent import BankLatent, CustomerLatent, DatedOutage, outage_multiplier_for_day
from sim.params import Params

_UNUSED_RNG = np.random.default_rng(0)  # outage_multiplier_for_day's rng param is unused by it

METHOD = "upi_autopay"  # sim.engine hardcodes every mandate to this method; mirrored here
CYCLE_LENGTH_DAYS = 30  # matches sim.engine's fixed 30-day cycle spacing / features.recovery
BASE_DATE = datetime(2026, 1, 1)


@dataclass
class AttemptEvent:
    """One beat in a single mandate's lifetime under one arm — an attempt actually made,
    or a non-attempt terminal decision (`dobara`'s stop/abstain/escalate) — with the
    notification burden accumulated to that point.

    Recorded only when a caller passes `trace=True` to `run_arm` (default `False`, so the
    30-seed harness, the sensitivity sweep and every existing caller allocate nothing and
    behave byte-for-byte as before). The one consumer today is
    `scripts/build_home_demo.py`, which needs a real, per-beat reconstruction of one
    mandate under two arms for the landing page's side-by-side demonstration — the
    aggregate `MandateResult` fields below can say *how many* notifications an arm sent
    but not *when*, and inventing that ordering for the page would be exactly the kind of
    unsourced number CLAUDE.md forbids.
    """

    cycle_index: int
    attempt_index: int
    kind: str  # "attempt" | "stop" | "abstain" | "escalate" | "offer_date_change"
    at: str  # ISO-8601, the moment the action is taken
    channel: str | None  # notification channel for this beat, when one was sent
    outcome: str | None  # sim.engine.attempt_outcome's outcome, for kind == "attempt"
    notifications_to_date: int  # res.n_notifications after this beat
    revoked: bool  # did the mandate revoke as a result of this beat
    reason: str | None  # stop/abstain/escalate reason, verbatim from the emitted action
    ltv_lost_inr: float  # res.ltv_lost_inr after this beat (0.0 until a revocation)


@dataclass
class MandateResult:
    """Realized outcomes for one mandate under one arm. Aggregated across mandates (and,
    for the sensitivity sweep / batch harness, across seeds) by the caller.
    """

    mandate_id: int
    bank_id: str
    method: str
    merchant_category: str
    is_cold_start: bool
    regime_shift_bank: bool
    amount: float
    n_attempts: int = 0
    n_successes: int = 0
    n_notifications: int = 0
    n_hard_declines: int = 0
    n_human_escalations: int = 0
    n_abstentions: int = 0
    gross_recovered_inr: float = 0.0
    notification_cost_inr: float = 0.0
    revoked: bool = False
    revoked_at_cycle: int | None = None
    ltv_lost_inr: float = 0.0
    attempts_in_outage_window: int = 0
    routed_to_holdout: bool = False
    success_attempt_indices: list[int] = field(default_factory=list)
    # Per-cycle failure/recovery bookkeeping, mirroring sim.engine.SimSummary's own
    # recovery_rate definition exactly (n_cycles_with_failure_then_recovery /
    # n_cycles_with_failure -- "of failed cycles", per docs/07-EVAL-SPEC.md's metric
    # table) rather than the mandate-lifetime `n_attempts > 1` proxy this harness used
    # before 2026-08-25 -- see docs/DECISIONS.md for why that proxy was wrong (it read
    # 0.97-1.00 here against a >1.0-scale-incompatible published Phase 1 benchmark of
    # 0.28-0.48, a different denominator entirely, not just a different number).
    n_cycles_with_failure: int = 0
    n_cycles_with_failure_then_recovery: int = 0
    # attempts actually used in cycles whose first attempt failed -- the metric that
    # actually reflects a cadence's retry ceiling; see docs/DECISIONS.md "aggressive_8x
    # investigation" for why the mandate-lifetime attempts_mean cannot show this (~90% of
    # cycles never fail at all, diluting any cadence difference in the aggregate).
    attempts_in_failed_cycles: int = 0
    # Cumulative-to-date (gross_recovered_inr / net_ltv_inr) snapshot at the end of each
    # cycle actually run, in order -- purely additive bookkeeping for
    # scripts/build_money_chart.py's per-cycle money-over-time chart. Never read by the
    # 30-seed harness (eval/run.py) or the sensitivity sweep; adding it changes no
    # existing field's value. Shorter than `population.n_cycles` for a mandate that
    # revoked or hard-declined before the last cycle -- the caller pads by repeating the
    # final value, since a revoked mandate's cumulative total simply stops moving.
    per_cycle_gross_inr: list[float] = field(default_factory=list)
    per_cycle_net_inr: list[float] = field(default_factory=list)
    # Per-beat trace, empty unless the caller asked for it (`run_arm(..., trace=True)`).
    # See AttemptEvent above.
    events: list[AttemptEvent] = field(default_factory=list)

    @property
    def net_ltv_inr(self) -> float:
        return self.gross_recovered_inr - self.ltv_lost_inr - self.notification_cost_inr


@dataclass
class _MandateState:
    """Mutable per-mandate running state, mirroring `sim.engine._MandateState` plus the
    extra fields `agent.decide()` needs in a live `DecisionContext`."""

    cycle_day: int
    consecutive_failed_cycles: int = 0
    cumulative_failure_notifications: int = 0
    last_date_change_cycle: int | None = None  # last ACCEPTED change (sim.engine parity)
    date_change_last_offered_cycle_index: int | None = None  # last OFFERED, accepted or not
    n_attempts_to_date: int = 0
    n_successes_to_date: int = 0
    last_attempt_at: datetime | None = None
    last_attempt_outcome: str | None = None
    prev_error_source: str | None = None
    prev_error_step: str | None = None
    prev_error_reason: str | None = None
    has_declared_preferred_day: bool = False
    declared_preferred_day: int | None = None
    revoked: bool = False


def _due_date(cycle_index: int, cycle_day: int) -> datetime:
    return BASE_DATE.replace(day=1) + timedelta(days=30 * (cycle_index - 1) + (cycle_day - 1))


def _notification_cost(params: Params, channel: str) -> float:
    return float(params.get(f"notification.cost_inr.{channel}"))


def _is_outage_day(bank_id: str, at: datetime, dated_outages: list[DatedOutage]) -> bool:
    return any(ev.day == at.date() and ev.duration_hours > 0 for ev in dated_outages)


def _new_result(m: MandateSpec) -> MandateResult:
    return MandateResult(
        mandate_id=m.mandate_id,
        bank_id=m.customer.bank_id,
        method=METHOD,
        merchant_category=m.merchant_category,
        is_cold_start=m.is_cold_start,
        regime_shift_bank=m.regime_shift_bank,
        amount=m.amount,
    )


def _append_event(
    res: MandateResult,
    *,
    cycle_index: int,
    attempt_index: int,
    kind: str,
    at: datetime,
    channel: str | None = None,
    outcome: str | None = None,
    reason: str | None = None,
) -> None:
    """Appends one `AttemptEvent`, reading the notification/LTV totals off `res` itself so
    a trace can never disagree with the aggregate it accompanies."""
    res.events.append(
        AttemptEvent(
            cycle_index=cycle_index,
            attempt_index=attempt_index,
            kind=kind,
            at=at.isoformat(),
            channel=channel,
            outcome=outcome,
            notifications_to_date=res.n_notifications,
            revoked=res.revoked,
            reason=reason,
            ltv_lost_inr=res.ltv_lost_inr,
        )
    )


def _draw_attempt(
    res: MandateResult,
    state: _MandateState,
    bank: BankLatent,
    customer: CustomerLatent,
    at: datetime,
    amount: float,
    params: Params,
    dated_outages: list[DatedOutage],
    seed: int,
    mandate_id: int,
    cycle_index: int,
    attempt_index: int,
    bd_mult: float,
    prior_attempt_failed: bool,
    notifications_this_cycle: int,
    life_table: LifeTable,
    merchant_category: str,
    trace: bool = False,
    channel: str | None = None,
) -> str:
    """Draws one real attempt outcome (always with a valid PDN — every arm here sends
    one first), records it onto `res`/`state`, rolls the true revocation hazard on
    failure, and returns the outcome string. Shared by every arm so the bookkeeping
    cannot drift between them.

    `trace`/`channel` are the opt-in per-beat trace (see `AttemptEvent`): appending one
    record per attempt here, in the one function every arm's attempts already pass
    through, is what keeps a traced lane and a scored lane from ever disagreeing about
    what happened.
    """
    draw = attempt_outcome(
        bank,
        customer,
        at,
        amount,
        True,
        params,
        dated_outages,
        event_rng(seed, mandate_id, cycle_index, attempt_index, "outcome"),
        bd_mult,
        prior_attempt_failed,
    )
    res.n_attempts += 1
    state.n_attempts_to_date += 1
    state.last_attempt_at = at
    state.last_attempt_outcome = draw.outcome
    if _is_outage_day(bank.bank_id, at, dated_outages):
        res.attempts_in_outage_window += 1

    def _record() -> str:
        if trace:
            _append_event(
                res,
                cycle_index=cycle_index,
                attempt_index=attempt_index,
                kind="attempt",
                at=at,
                channel=channel,
                outcome=draw.outcome,
            )
        return draw.outcome

    if draw.outcome == "success":
        res.n_successes += 1
        res.success_attempt_indices.append(attempt_index)
        res.gross_recovered_inr += amount
        state.n_successes_to_date += 1
        return _record()
    if draw.outcome == "rejected_no_pdn":
        return _record()  # never fires here — every arm always sends a valid PDN first

    state.prev_error_source, state.prev_error_step, state.prev_error_reason = (
        draw.error_source,
        draw.error_step,
        draw.error_reason,
    )
    if draw.outcome == "hard_decline":
        res.n_hard_declines += 1
        return _record()

    state.cumulative_failure_notifications += 1
    hazard = revocation_hazard(
        params,
        customer,
        state.cumulative_failure_notifications,
        notifications_this_cycle,
        state.consecutive_failed_cycles + 1,
        cycle_index,
    )
    if event_rng(seed, mandate_id, cycle_index, attempt_index, "revocation").random() < hazard:
        state.revoked = True
        res.revoked = True
        res.revoked_at_cycle = cycle_index
        res.ltv_lost_inr = ltv_remaining(
            amount, life_table, merchant_category, cycle_index - 1, params
        )
    return _record()


def _maybe_offer_date_change(
    res: MandateResult,
    state: _MandateState,
    m: MandateSpec,
    cycle_index: int,
    notifications_this_cycle: int,
    fatigue_cap: int,
    response_rate: float,
    converge_n: int,
    world_seed: int,
    params: Params,
) -> int:
    """Mirrors `sim.engine.run_simulation`'s automatic date-change-offer block: fires
    unconditionally (not through `decide()`) after 2 consecutive failed cycles, gated by
    the same `converge_n` cap. This is a background mandate-level event every arm's
    mandates are equally exposed to, not a policy choice — `dobara`'s own live
    `OfferDateChange` candidate (only reachable once `has_declared_preferred_day` is
    already `True`, per `agent/decide.py`) is for *re-converging*, and needs this
    mechanic to have fired at least once first to have anything to converge from. See
    docs/DECISIONS.md [2026-08-25] "date-change-offer mechanic shared across arms".
    Returns the number of notifications this added (0 or 1).
    """
    if not (
        state.consecutive_failed_cycles >= 2
        and notifications_this_cycle < fatigue_cap
        and (
            state.last_date_change_cycle is None
            or cycle_index - state.last_date_change_cycle >= converge_n
        )
    ):
        return 0
    accepted = (
        event_rng(world_seed, m.mandate_id, cycle_index, "date_change_offer").random()
        < response_rate
    )
    res.n_notifications += 1
    res.notification_cost_inr += _notification_cost(params, "sms")
    state.date_change_last_offered_cycle_index = cycle_index
    if accepted:
        state.last_date_change_cycle = cycle_index
        new_day = int(min(28, max(1, m.customer.income_day + 2)))
        state.cycle_day = new_day
        state.has_declared_preferred_day = True
        state.declared_preferred_day = new_day
    return 1


def _end_of_cycle(
    state: _MandateState,
    res: MandateResult,
    cycle_succeeded: bool,
    had_failure: bool,
    attempts_this_cycle: int,
) -> None:
    if had_failure:
        state.consecutive_failed_cycles = (
            0 if cycle_succeeded else state.consecutive_failed_cycles + 1
        )
        res.n_cycles_with_failure += 1
        res.attempts_in_failed_cycles += attempts_this_cycle
        if cycle_succeeded:
            res.n_cycles_with_failure_then_recovery += 1
    elif cycle_succeeded:
        state.consecutive_failed_cycles = 0


def _snapshot_cycle(res: MandateResult) -> None:
    """Append this mandate's cumulative-to-date gross/net after a cycle actually ran.
    See `MandateResult.per_cycle_gross_inr`'s docstring."""
    res.per_cycle_gross_inr.append(res.gross_recovered_inr)
    res.per_cycle_net_inr.append(res.net_ltv_inr)


def _pad_cycle_history(res: MandateResult, n_cycles: int) -> None:
    """Extend a mandate's per-cycle history to `n_cycles` entries by repeating its final
    cumulative value -- a revoked/hard-declined mandate's totals simply stop moving."""
    last_gross = res.per_cycle_gross_inr[-1] if res.per_cycle_gross_inr else 0.0
    last_net = res.per_cycle_net_inr[-1] if res.per_cycle_net_inr else 0.0
    while len(res.per_cycle_gross_inr) < n_cycles:
        res.per_cycle_gross_inr.append(last_gross)
    while len(res.per_cycle_net_inr) < n_cycles:
        res.per_cycle_net_inr.append(last_net)


def _run_cadence_arm(
    world: World, cadence: Cadence, params: Params, life_table: LifeTable, trace: bool = False
) -> list[MandateResult]:
    """`do_nothing` / `razorpay_default` / `aggressive_8x` — a fixed attempt cadence,
    replicated bug-for-bug against `sim.engine.run_simulation`'s existing loop shape so
    `razorpay_default` cannot silently drift from the policy that generated Phase 1/2's
    own training data.
    """
    n_cycles = int(params.get("population.n_cycles"))
    fresh_pdn_required = bool(params.get("retry_policy.retry_requires_fresh_pdn"))
    fatigue_cap = int(params.get("notification.fatigue_cap_per_cycle"))
    response_rate = float(params.get("date_change_offer.response_rate"))
    converge_n = int(params.get("date_change_offer.converge_max_changes_per_n_cycles"))
    regime_from_cycle = int(params.get("regime_shift.applies_from_cycle_index"))
    regime_bd_mult = float(params.get("regime_shift.shift_multiplier_bd"))

    results = []
    for m in world.mandates:
        bank = world.banks[m.customer.bank_id]
        state = _MandateState(cycle_day=m.cycle_day)
        res = _new_result(m)

        for cycle_index in range(1, n_cycles + 1):
            if state.revoked:
                break
            due_date = _due_date(cycle_index, state.cycle_day)
            bd_mult = (
                regime_bd_mult
                if (m.regime_shift_bank and cycle_index >= regime_from_cycle)
                else 1.0
            )
            notifications_this_cycle = 0
            cycle_succeeded = False
            had_failure = False
            prior_attempt_failed = False
            attempts_this_cycle = 0

            if cadence.offers_date_change:
                notifications_this_cycle += _maybe_offer_date_change(
                    res,
                    state,
                    m,
                    cycle_index,
                    notifications_this_cycle,
                    fatigue_cap,
                    response_rate,
                    converge_n,
                    world.seed,
                    params,
                )

            for attempt_index in range(1, cadence.max_attempts + 1):
                if (
                    cadence.respects_fatigue_cap
                    and notifications_this_cycle >= fatigue_cap
                    and attempt_index > 1
                ):
                    break
                scheduled_at = due_date + timedelta(
                    hours=cadence.min_gap_hours * (attempt_index - 1)
                )
                if fresh_pdn_required or attempt_index == 1:
                    notifications_this_cycle += 1
                    res.n_notifications += 1
                    res.notification_cost_inr += _notification_cost(params, "sms")

                outcome = _draw_attempt(
                    res,
                    state,
                    bank,
                    m.customer,
                    scheduled_at,
                    m.amount,
                    params,
                    world.dated_outages,
                    world.seed,
                    m.mandate_id,
                    cycle_index,
                    attempt_index,
                    bd_mult,
                    prior_attempt_failed,
                    notifications_this_cycle,
                    life_table,
                    m.merchant_category,
                    trace,
                    "sms",
                )
                attempts_this_cycle += 1
                prior_attempt_failed = outcome in ("soft_decline", "hard_decline")

                if outcome == "success":
                    cycle_succeeded = True
                    break
                if outcome == "rejected_no_pdn":
                    continue
                had_failure = True
                if outcome == "hard_decline" or state.revoked:
                    break

            _end_of_cycle(state, res, cycle_succeeded, had_failure, attempts_this_cycle)
            _snapshot_cycle(res)
            if state.revoked:
                break

        _pad_cycle_history(res, n_cycles)
        results.append(res)
    return results


def _run_dobara_arm(
    world: World,
    params: Params,
    policy: PolicyConfig,
    model_bundle: ModelBundle,
    life_table: LifeTable,
    holdout_fraction: float,
    audit_trail: AuditTrail | None = None,
    trace: bool = False,
) -> list[MandateResult]:
    """Calls `agent.decide()` live once per attempt decision point. Mandates routed to
    the permanent holdout slice (`config/policy.yaml`'s `holdout_fraction`, per
    docs/07-EVAL-SPEC.md "## The permanent holdout arm") are run through
    `razorpay_default`'s fixed cadence instead and flagged `routed_to_holdout=True`, so
    the caller can report recovery lift on the served population against this control
    slice — never silently folded into the aggregate.

    `audit_trail`, added 2026-08-26 for the Phase 5 API (`api/live.py`): when supplied,
    every live `decide()` call also appends its `(ctx, decision)` pair to it — purely
    additive, `None` by default, so every existing caller (the Phase 4 batch harness) is
    byte-for-byte unaffected. Lets the API reuse this exact, already-tested decision loop
    for the Control Room's audit trail instead of re-deriving the context-building logic
    a second time.
    """
    n_cycles = int(params.get("population.n_cycles"))
    fatigue_cap = int(params.get("notification.fatigue_cap_per_cycle"))
    response_rate = float(params.get("date_change_offer.response_rate"))
    converge_n = int(params.get("date_change_offer.converge_max_changes_per_n_cycles"))
    regime_from_cycle = int(params.get("regime_shift.applies_from_cycle_index"))
    regime_bd_mult = float(params.get("regime_shift.shift_multiplier_bd"))
    max_attempts_cap = int(policy.get("max_attempts_per_cycle"))
    rp_cadence = razorpay_default_cadence(params)
    afa_threshold = float(params.get("afa.threshold_inr"))

    results = []
    for m in world.mandates:
        route_to_holdout = (
            event_rng(world.seed, m.mandate_id, "holdout_route").random() < holdout_fraction
        )
        if route_to_holdout:
            holdout_world = World(
                seed=world.seed, banks=world.banks, dated_outages=world.dated_outages, mandates=[m]
            )
            res = _run_cadence_arm(holdout_world, rp_cadence, params, life_table, trace)[0]
            res.routed_to_holdout = True
            results.append(res)
            continue

        bank = world.banks[m.customer.bank_id]
        state = _MandateState(cycle_day=m.cycle_day)
        res = _new_result(m)

        for cycle_index in range(1, n_cycles + 1):
            if state.revoked:
                break
            due_date = _due_date(cycle_index, state.cycle_day)
            cycle_end = due_date + timedelta(days=CYCLE_LENGTH_DAYS)
            bd_mult = (
                regime_bd_mult
                if (m.regime_shift_bank and cycle_index >= regime_from_cycle)
                else 1.0
            )
            notifications_this_cycle = 0
            notification_cost_this_cycle = 0.0
            cycle_succeeded = False
            had_failure = False
            prior_attempt_failed = False
            attempts_this_cycle = 0
            now = due_date

            notifications_this_cycle += _maybe_offer_date_change(
                res,
                state,
                m,
                cycle_index,
                notifications_this_cycle,
                fatigue_cap,
                response_rate,
                converge_n,
                world.seed,
                params,
            )

            attempt_index = 1
            while attempt_index <= max_attempts_cap:
                ctx = DecisionContext(
                    mandate_id=m.mandate_id,
                    cycle_id=cycle_index,
                    cycle_index=cycle_index,
                    merchant_category=m.merchant_category,
                    bank_id=m.customer.bank_id,
                    method=METHOD,
                    amount=m.amount,
                    afa_threshold_applicable=m.amount > afa_threshold,
                    now=now,
                    cycle_due_date=due_date,
                    cycle_end=cycle_end,
                    attempt_index=attempt_index,
                    last_attempt_at=state.last_attempt_at,
                    last_attempt_outcome=state.last_attempt_outcome,
                    n_attempts_to_date=state.n_attempts_to_date,
                    n_successes_to_date=state.n_successes_to_date,
                    prior_failures_this_cycle=attempt_index - 1,
                    consecutive_failed_cycles=state.consecutive_failed_cycles,
                    prev_error_source=state.prev_error_source,
                    prev_error_step=state.prev_error_step,
                    prev_error_reason=state.prev_error_reason,
                    failure_notifications_this_cycle=notifications_this_cycle,
                    total_contacts_30d=state.cumulative_failure_notifications,
                    days_since_first_failure_this_cycle=0 if attempt_index == 1 else 1,
                    has_customer_engaged_with_notice=False,
                    notifications_sent_this_cycle=notifications_this_cycle,
                    notification_cost_spent_this_cycle_inr=notification_cost_this_cycle,
                    last_pdn_sent_at=state.last_attempt_at,
                    has_declared_preferred_day=state.has_declared_preferred_day,
                    declared_preferred_day=state.declared_preferred_day,
                    date_change_last_offered_cycle_index=state.date_change_last_offered_cycle_index,
                    customer_opted_out=False,
                    mandate_revoked=state.revoked,
                )
                decision = decide(ctx, model_bundle, policy)
                if audit_trail is not None:
                    audit_trail.append(ctx, decision)
                action = decision.chosen

                if isinstance(action, Stop):
                    if trace:
                        _append_event(
                            res,
                            cycle_index=cycle_index,
                            attempt_index=attempt_index,
                            kind="stop",
                            at=now,
                            reason=action.reason.value,
                        )
                    break
                if isinstance(action, EscalateToHuman):
                    res.n_human_escalations += 1
                    if trace:
                        _append_event(
                            res,
                            cycle_index=cycle_index,
                            attempt_index=attempt_index,
                            kind="escalate",
                            at=now,
                            reason=action.reason,
                        )
                    break

                if isinstance(action, Abstain):
                    # CLAUDE.md: "when in doubt, the agent stops." Abstain means decide()
                    # lacks enough confidence to act — it must not attempt anyway. Prior
                    # behavior here silently fell back to a razorpay_default-style attempt
                    # on abstention, contradicting that non-negotiable; the user overruled
                    # docs/06-AGENT-SPEC.md's original "falls back to the documented
                    # default policy" design explicitly. See docs/DECISIONS.md
                    # [2026-08-25] "Abstain must stop, not fall back to an attempt".
                    # `Abstain` stays a distinct emitted action from `Stop` in decide()
                    # itself (the audit trail should still say *why*: genuine uncertainty
                    # vs. a confident negative-EV call) but mechanically it now behaves
                    # exactly like `Stop` here: no notification, no draw, no attempt.
                    res.n_abstentions += 1
                    if trace:
                        _append_event(
                            res,
                            cycle_index=cycle_index,
                            attempt_index=attempt_index,
                            kind="abstain",
                            at=now,
                            reason=action.reason.value,
                        )
                    break

                if isinstance(action, OfferDateChange):
                    # Recorded immediately, accepted or not — this is the field
                    # DOBARA-CONVERGE actually gates on (`agent/compliance.py::_dobara_converge`
                    # reads `date_change_last_offered_cycle_index`, not the accept-only
                    # `last_date_change_cycle` below). Without this, a declined offer would
                    # leave the same OfferDateChange candidate legal on the very next
                    # iteration, looping until DOBARA-FATIGUE's notification cap eventually
                    # bites — correct in the end but wastefully slow; setting this here makes
                    # the gate do its job on the very next call. See docs/DECISIONS.md
                    # [2026-08-25] "dobara arm: fixed a date-change-offer re-offer loop".
                    state.date_change_last_offered_cycle_index = cycle_index
                    notifications_this_cycle += 1
                    res.n_notifications += 1
                    cost = _notification_cost(params, action.channel.value)
                    notification_cost_this_cycle += cost
                    res.notification_cost_inr += cost
                    if trace:
                        _append_event(
                            res,
                            cycle_index=cycle_index,
                            attempt_index=attempt_index,
                            kind="offer_date_change",
                            at=now,
                            channel=action.channel.value,
                        )
                    accepted = (
                        event_rng(
                            world.seed,
                            m.mandate_id,
                            cycle_index,
                            attempt_index,
                            "date_change_response",
                        ).random()
                        < response_rate
                    )
                    if accepted:
                        state.last_date_change_cycle = cycle_index
                        state.cycle_day = action.new_preferred_day
                    now = due_date
                    continue  # re-decide; doesn't consume an attempt slot

                if isinstance(action, ScheduleDebit):
                    notifications_this_cycle += 1
                    res.n_notifications += 1
                    cost = _notification_cost(params, action.notice.channel.value)
                    notification_cost_this_cycle += cost
                    res.notification_cost_inr += cost
                    outcome = _draw_attempt(
                        res,
                        state,
                        bank,
                        m.customer,
                        action.t,
                        m.amount,
                        params,
                        world.dated_outages,
                        world.seed,
                        m.mandate_id,
                        cycle_index,
                        attempt_index,
                        bd_mult,
                        prior_attempt_failed,
                        notifications_this_cycle,
                        life_table,
                        m.merchant_category,
                        trace,
                        action.notice.channel.value,
                    )
                    attempts_this_cycle += 1
                    prior_attempt_failed = outcome in ("soft_decline", "hard_decline")
                    if outcome == "success":
                        cycle_succeeded = True
                        break
                    if outcome != "rejected_no_pdn":
                        had_failure = True
                    if outcome == "hard_decline" or state.revoked:
                        break
                    attempt_index += 1
                    now = action.t
                    continue

                raise TypeError(f"unhandled action {type(action).__name__}")  # pragma: no cover

            _end_of_cycle(state, res, cycle_succeeded, had_failure, attempts_this_cycle)
            _snapshot_cycle(res)
            if state.revoked:
                break

        _pad_cycle_history(res, n_cycles)
        results.append(res)
    return results


def _norm_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def _true_p_success(
    bank: BankLatent,
    customer: CustomerLatent,
    at: datetime,
    amount: float,
    params: Params,
    dated_outages: list[DatedOutage],
    bd_mult: float,
    prior_attempt_failed: bool,
) -> float:
    """The exact closed-form `P(success)` under `sim.engine.attempt_outcome`'s true
    generative model, for `_run_oracle_arm` only — the expectation taken *analytically*
    over `sim.latent.balance_available`'s log-normal noise (`mean=0, sigma=0.35`), rather
    than by drawing one realized sample. This is knowledge oracle is entitled to (the true
    generating probability), not a peek at one coin flip's outcome — oracle still faces
    the real stochastic draw when it actually attempts (`_draw_attempt`). Mirrors
    `attempt_outcome`'s td/bd/`raw_fail_prob`/correlation arithmetic exactly (see
    `sim/engine.py`) so this is provably that function's true success probability, not an
    approximation of it.
    """
    dow_weight = bank.dow_weights[at.weekday()]
    outage_mult = outage_multiplier_for_day(bank.bank_id, at.date(), dated_outages, _UNUSED_RNG)
    td = min(bank.base_td * (2 - dow_weight) * (2 - outage_mult), 0.5)
    bd_if_funds = min(bank.base_bd * (2 - dow_weight) * bd_mult, 0.9)
    bd_if_no_funds = max(bd_if_funds, 0.85)

    days_since_income = (at.day - customer.income_day) % 30
    expected_balance = customer.income_amount * (
        (1 - customer.spend_decay_per_day) ** days_since_income
    )
    if expected_balance <= 0:
        p_funds = 0.0
    else:
        threshold = amount / expected_balance
        p_funds = 1.0 if threshold <= 0 else 1.0 - _norm_cdf(math.log(threshold) / 0.35)

    raw_fail_prob = p_funds * min(td + bd_if_funds, 0.98) + (1 - p_funds) * min(
        td + bd_if_no_funds, 0.98
    )
    fail_prob = raw_fail_prob
    if prior_attempt_failed:
        corr = float(params.get("retry_policy.within_cycle_repeat_failure_correlation"))
        fail_prob = corr + (1 - corr) * raw_fail_prob
    return 1.0 - fail_prob


def _run_oracle_arm(world: World, params: Params, life_table: LifeTable) -> list[MandateResult]:
    """The ceiling: perfect foresight over latent state, per docs/07-EVAL-SPEC.md. Picks
    its attempt day per cycle from the customer's deterministic expected-balance curve
    (no rng — this is knowledge the agent could never have, not a lucky draw) and skips
    any dated-outage day it independently knows about, **and, before every attempt,
    stops the cycle the instant the true expected net value of attempting again is not
    positive** — `E[net] = p_success_true*amount - (1-p_success_true)*p_revoke_true*ltv -
    cost`, using `_true_p_success` and the real `sim.engine.revocation_hazard` (both
    exact, not estimated), correctly weighting the revocation-hazard term by the true
    probability of failure since only a failed attempt can trigger a revocation roll. This
    is what makes it an actual ceiling rather than just `razorpay_default` with slightly
    better day-picking: no other arm can retry more selectively than a policy that knows
    the true probabilities. It still faces the same stochastic bank-side draw
    (`attempt_outcome`) as every other arm for whichever attempts it does make —
    foresight over the generating probabilities does not mean foreknowledge of one coin
    flip's result.
    """
    n_cycles = int(params.get("population.n_cycles"))
    max_attempts = int(params.get("retry_policy.max_attempts_default_policy"))
    min_gap_hours = int(params.get("retry_policy.min_gap_hours_between_attempts"))
    regime_from_cycle = int(params.get("regime_shift.applies_from_cycle_index"))
    regime_bd_mult = float(params.get("regime_shift.shift_multiplier_bd"))
    notification_cost = _notification_cost(params, "sms")

    results = []
    for m in world.mandates:
        bank = world.banks[m.customer.bank_id]
        state = _MandateState(cycle_day=m.cycle_day)
        res = _new_result(m)

        for cycle_index in range(1, n_cycles + 1):
            if state.revoked:
                break
            due_date = _due_date(cycle_index, state.cycle_day)
            bd_mult = (
                regime_bd_mult
                if (m.regime_shift_bank and cycle_index >= regime_from_cycle)
                else 1.0
            )

            best_day = due_date
            best_expected = -1.0
            for offset in range(CYCLE_LENGTH_DAYS):
                day = due_date + timedelta(days=offset)
                days_since_income = (day.day - m.customer.income_day) % 30
                expected_balance = m.customer.income_amount * (
                    (1 - m.customer.spend_decay_per_day) ** days_since_income
                )
                if _is_outage_day(bank.bank_id, day, world.dated_outages):
                    continue
                if expected_balance > best_expected:
                    best_expected = expected_balance
                    best_day = day

            notifications_this_cycle = 0
            cycle_succeeded = False
            had_failure = False
            prior_attempt_failed = False
            attempts_this_cycle = 0

            for attempt_index in range(1, max_attempts + 1):
                scheduled_at = best_day + timedelta(hours=min_gap_hours * (attempt_index - 1))

                p_success_true = _true_p_success(
                    bank,
                    m.customer,
                    scheduled_at,
                    m.amount,
                    params,
                    world.dated_outages,
                    bd_mult,
                    prior_attempt_failed,
                )
                p_revoke_true = revocation_hazard(
                    params,
                    m.customer,
                    state.cumulative_failure_notifications + 1,
                    notifications_this_cycle + 1,
                    state.consecutive_failed_cycles + 1,
                    cycle_index,
                )
                ltv = ltv_remaining(
                    m.amount, life_table, m.merchant_category, cycle_index - 1, params
                )
                e_net = (
                    p_success_true * m.amount
                    - (1 - p_success_true) * p_revoke_true * ltv
                    - notification_cost
                )
                if e_net <= 0:
                    break  # true expected value doesn't justify another attempt this cycle

                notifications_this_cycle += 1
                res.n_notifications += 1
                res.notification_cost_inr += notification_cost

                outcome = _draw_attempt(
                    res,
                    state,
                    bank,
                    m.customer,
                    scheduled_at,
                    m.amount,
                    params,
                    world.dated_outages,
                    world.seed,
                    m.mandate_id,
                    cycle_index,
                    attempt_index,
                    bd_mult,
                    prior_attempt_failed,
                    notifications_this_cycle,
                    life_table,
                    m.merchant_category,
                )
                attempts_this_cycle += 1
                prior_attempt_failed = outcome in ("soft_decline", "hard_decline")

                if outcome == "success":
                    cycle_succeeded = True
                    break
                if outcome == "rejected_no_pdn":
                    continue
                had_failure = True
                if outcome == "hard_decline" or state.revoked:
                    break

            _end_of_cycle(state, res, cycle_succeeded, had_failure, attempts_this_cycle)
            _snapshot_cycle(res)
            if state.revoked:
                break

        _pad_cycle_history(res, n_cycles)
        results.append(res)
    return results


def run_arm(
    world: World,
    arm: Arm,
    params: Params,
    life_table: LifeTable,
    policy: PolicyConfig | None = None,
    model_bundle: ModelBundle | None = None,
    holdout_fraction: float = 0.0,
    audit_trail: AuditTrail | None = None,
    trace: bool = False,
) -> list[MandateResult]:
    """Dispatch by arm name. `policy`/`model_bundle` are required for `dobara` only;
    `holdout_fraction` and `audit_trail` are consumed only by `dobara`
    (docs/07-EVAL-SPEC.md's permanent holdout arm; `audit_trail` for the Phase 5 API).

    `trace=True` additionally records a per-beat `AttemptEvent` list on every returned
    `MandateResult` (see that dataclass); it changes no draw, no ordering and no scored
    field, and is not supported by `oracle`, which no consumer needs traced."""
    if arm is Arm.DO_NOTHING:
        return _run_cadence_arm(world, DO_NOTHING_CADENCE, params, life_table, trace)
    if arm is Arm.RAZORPAY_DEFAULT:
        return _run_cadence_arm(world, razorpay_default_cadence(params), params, life_table, trace)
    if arm is Arm.AGGRESSIVE_8X:
        return _run_cadence_arm(world, aggressive_8x_cadence(params), params, life_table, trace)
    if arm is Arm.ORACLE:
        return _run_oracle_arm(world, params, life_table)
    if arm is Arm.DOBARA:
        if policy is None or model_bundle is None:
            raise ValueError("dobara arm requires policy and model_bundle")
        return _run_dobara_arm(
            world, params, policy, model_bundle, life_table, holdout_fraction, audit_trail, trace
        )
    raise ValueError(f"unknown arm {arm}")  # pragma: no cover
