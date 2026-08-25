"""The policy: `decide(ctx, models, config) -> Decision`. Per docs/06-AGENT-SPEC.md,
this is a **pure function** — no I/O, no network, no clock (`ctx.now` is supplied, never
`datetime.now()`), **no LLM import anywhere** (enforced by
`tests/test_no_llm_in_money_path.py`). Everything it needs arrives in `DecisionContext`
and `ModelBundle`; the only side-effecting step (loading models/DB) lives in
`agent/models.py::load_model_bundle`, called by the caller before `decide()` runs.

## Candidate generation

Per docs/06-AGENT-SPEC.md "## Candidate generation" and docs/02-ARCHITECTURE.md "## The
bounded action set":

1. `ScheduleDebit(t)` candidates for each remaining day in the legal window
   (`now + 24h` through `cycle_end`), one per `Channel` for the paired
   `SendPreDebitNotice` (`notice.t == t - 24h`, satisfying `RBI-PDN-24H` at the
   boundary). **`SendPreDebitNotice` is never generated as a free-standing top-level
   candidate in this build** — every notice the agent proposes is in service of a
   specific debit time; there is no scenario in this decision model where sending a
   notice without a proposed debit has its own scoreable `E[net]`. `agent/actions.py`'s
   `SendPreDebitNotice` type still exists standalone (the compliance gate treats it
   identically to the notice embedded in a `ScheduleDebit`), for a future build that adds
   reminder-only contact.
2. `OfferDateChange(t)` candidates, same day range, gated by `DOBARA-CONVERGE` — only
   constructed at all when the customer has a declared or evidenced-stable day to move
   toward (`ctx.has_declared_preferred_day`), since otherwise there is nothing to offer.
3. Two baseline candidates always present, per the architecture doc's "STOP and
   ESCALATE_TO_HUMAN are always in the candidate set": `Stop(NEGATIVE_EXPECTED_VALUE)`
   and `EscalateToHuman(...)`, both scored at `E[net] = 0.0` — "doing nothing" is the
   zero-cost, zero-gain baseline every real action must beat. Because Python's sort is
   stable and `Stop` is listed first, `Stop` wins ties with `EscalateToHuman` when no real
   action clears zero — in this build `EscalateToHuman` is reachable, gated, and scored,
   but its selection as the emitted action (rather than a considered-and-rejected
   alternative) is deferred to the human-facing proposal queue (Phase 5); see
   `docs/DECISIONS.md` [2026-08-25] "ESCALATE_TO_HUMAN scoring".

Every candidate is checked against `agent/compliance.py::is_hard_compliant` before it is
allowed into the scored pool — the gate runs **inside** candidate generation, not as a
post-hoc filter, per the spec's "structural enforcement, not advisory."

## Scoring

`E[net|a] = P(success|t_a)*amount - P(revoke|attempts+1,...)*LTV_remaining -
cost(channel_a)`, per docs/02-ARCHITECTURE.md "## The decision, formally". `P(success)`
comes from `models.recovery` (Model 1, `models/recovery.py`), `P(revoke)` from
`models.hazard` (Model 2, `models/hazard.py`) — **`hazard_per_failure_notification` is a
declared assumption in `sim/params.yaml`, recalibrated 2026-08-25; the hazard model's
prediction here is only as trustworthy as that assumption, which is exactly why
`min_slice_n`/`max_slice_brier`/change-point abstention exists below rather than trusting
every prediction blindly** (see `docs/DECISIONS.md` [2026-08-25] "Corrected: the hazard
headline number does not confirm the thesis"). `LTV_remaining` comes from
`models.life_table` (`models/ltv.py`, a transparent life-table estimate, not a model
prediction). `cost` is read from `sim/params.yaml`'s `notification.cost_inr.*`.

**Confidence band, an approximation, stated honestly — deliberately not called "CI".**
Neither model exposes a per-prediction posterior. Rather than inventing one, the band
here is a **Wilson score interval** on each probability (`_wilson_interval`), using the
*slice's* observation count (`ModelBundle.recovery_slices_by_bank` /
`hazard_slices_by_method`, from the training-time slice metrics) as the effective sample
size behind that calibrated probability. Wilson, not the normal approximation
(`p +/- z*sqrt(p*(1-p)/n)`): the normal approximation undercovers at small `n` and near
`p` = 0 or 1 — precisely the thin-slice, low-hazard regime this band exists to adjudicate
for `ABSTAIN` — and it isn't even bounded to `[0, 1]` there, whereas Wilson is bounded by
construction. This is not a full predictive posterior — it is a reproducible, principled
uncertainty band that (correctly) widens for thin slices and tightens for well-observed
ones, propagated through the linear `E[net]` formula by interval arithmetic (worst case:
low `p_success`, high `p_revoke`; best case: the reverse). Documented as an
approximation, not oversold as a calibrated posterior. **Called `confidence_band`, never
`confidence_interval`/"CI"**, throughout `Decision` and the audit renderer — Phase 4's
evaluation harness produces real bootstrap/seed-variance confidence intervals over
`artifacts/summary.json` metrics, and that is the only place "CI" should appear. The two
are statistically unrelated (this one approximates uncertainty in a single calibrated
probability at decision time; that one measures variance across simulated seeds), and
labelling both "CI" would let this acknowledged approximation borrow the authority of a
sound estimate. See `docs/DECISIONS.md` [2026-08-25].

## Abstention

Per docs/06-AGENT-SPEC.md "## Abstention". Checked *before* scoring commits to a real
action (a `ScheduleDebit`/`OfferDateChange` winner) — an untrustworthy model should not
even be allowed to win the argmax:

- `(bank, method)` slice `n` below `config.min_slice_n` (checked against the recovery
  model's per-bank slice; the hazard model's slices are keyed by method only, per
  `models/hazard.py::_slice_metrics`, so bank-level thinness is the binding constraint).
- A detected bank-health change-point at `ctx.now` (`ModelBundle.bank_health`, the same
  EWMA change-point flag `features/recovery.py` joins as-of for `bank_health_changepoint`).
- Slice calibration error (`brier_score.point`) exceeding `config.max_slice_brier`, on
  either the recovery bank-slice or the hazard method-slice.
- The confidence band on the winning real action's `E[net]` straddling zero.

On any trigger the chosen action becomes `Abstain(reason)`; `agent/audit.py`'s renderer
is responsible for stating the documented-baseline-policy fallback in the human-readable
line — `decide()` itself only names *why*, per the pure-function/no-I/O boundary.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

import pandas as pd

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
from agent.compliance import TEMPLATE_DATE_CHANGE, TEMPLATE_PDN, evaluate, is_hard_compliant
from agent.context import (
    ClauseRef,
    Decision,
    DecisionContext,
    Money,
    RejectedAlternative,
    RupeeMath,
)
from agent.models import ModelBundle
from agent.policy import PolicyConfig
from agent.stopping import StoppingReason
from features.hazard import HAZARD_FEATURE_COLUMNS, amount_band
from features.recovery import CYCLE_LENGTH_DAYS, RECOVERY_FEATURE_COLUMNS
from models.ltv import ltv_remaining

AFA_THRESHOLD_INR = 15000.0
DEBIT_HOUR = 10  # a fixed representative in-window hour; CONDUCT-HOURS is 08:00-19:00
Z_95 = 1.959964  # two-sided 95% critical value, for the slice-n Wilson confidence band


def decide(ctx: DecisionContext, models: ModelBundle, config: PolicyConfig) -> Decision:
    terminal = _terminal_stop(ctx)
    if terminal is not None:
        return terminal

    candidates = _generate_candidates(ctx, config)
    legal = [a for a in candidates if is_hard_compliant(a, ctx, config)]
    scores = _score_all(legal, ctx, models)
    scored = list(zip(legal, scores, strict=True))
    scored.sort(key=lambda pair: pair[1].expected_net, reverse=True)

    best_action, best = scored[0]
    rejected = [
        RejectedAlternative(
            description=_describe(a), expected_net=s.expected_net, reason=_reject_reason(s, best)
        )
        for a, s in scored[1:]
    ]

    satisfied, blocked = evaluate(best_action, ctx, config)
    clauses_satisfied = [ClauseRef(r.id, r.citation) for r in satisfied]
    clauses_blocked = [ClauseRef(r.id, r.citation) for r in blocked]

    chosen: Action = best_action
    stopping_reason: StoppingReason | None = (
        best_action.reason if isinstance(best_action, Stop) else None
    )

    if isinstance(best_action, ScheduleDebit | OfferDateChange):
        abstain_reason = _abstention_reason(ctx, models, config, best)
        if abstain_reason is not None:
            chosen = Abstain(reason=abstain_reason)
            stopping_reason = StoppingReason.INSUFFICIENT_CONFIDENCE

    requires_signoff = ctx.amount > float(config.get("human_signoff_threshold_inr")) or isinstance(
        chosen, EscalateToHuman
    )

    return Decision(
        chosen=chosen,
        expected_net=best.expected_net,
        confidence_band=(best.band_lo, best.band_hi),
        rejected_alternatives=rejected,
        clauses_satisfied=clauses_satisfied,
        clauses_blocked=clauses_blocked,
        rupee_math=best.rupee_math,
        model_versions=models.model_versions,
        feature_attribution=best.feature_attribution,
        stopping_reason=stopping_reason,
        requires_signoff=requires_signoff,
    )


def _terminal_stop(ctx: DecisionContext) -> Decision | None:
    """Preconditions that make the whole legal candidate space moot — there is nothing
    left to schedule, notify, or offer. Checked before candidate generation rather than
    as scored candidates, since none of them compete on `E[net]`; they are absolute.
    """
    reason: StoppingReason | None = None
    if ctx.mandate_revoked:
        reason = StoppingReason.MANDATE_REVOKED
    elif ctx.customer_opted_out:
        reason = StoppingReason.CUSTOMER_OPTED_OUT
    elif ctx.last_attempt_outcome == "hard_decline":
        reason = StoppingReason.HARD_DECLINE
    else:
        return None

    zero_math = RupeeMath(
        p_success=0.0, amount=0.0, p_revoke=0.0, ltv_remaining=0.0, cost=0.0, expected_net=0.0
    )
    return Decision(
        chosen=Stop(reason=reason),
        expected_net=0.0,
        confidence_band=(0.0, 0.0),
        rejected_alternatives=[],
        clauses_satisfied=[],
        clauses_blocked=[],
        rupee_math=zero_math,
        model_versions={},
        feature_attribution={},
        stopping_reason=reason,
        requires_signoff=False,
    )


def _generate_candidates(ctx: DecisionContext, config: PolicyConfig) -> list[Action]:
    """The baseline pair (`Stop`, `EscalateToHuman`, both scored at `E[net] = 0.0` — see
    module docstring) always leads the candidate list. When `MAX_ATTEMPTS`/`COST_CAP`
    already precludes any further legal debit/notice this cycle, the `Stop` baseline
    carries that specific reason instead of the generic `NEGATIVE_EXPECTED_VALUE`, and no
    real candidates are generated at all — there is nothing left to score.
    """
    if ctx.attempt_index > int(config.get("max_attempts_per_cycle")):
        return [
            Stop(reason=StoppingReason.MAX_ATTEMPTS),
            EscalateToHuman(reason="max attempts this cycle reached"),
        ]
    if ctx.notification_cost_spent_this_cycle_inr >= float(config.get("cost_cap_inr")):
        return [
            Stop(reason=StoppingReason.COST_CAP),
            EscalateToHuman(reason="notification cost cap reached this cycle"),
        ]

    window_start = ctx.now + timedelta(hours=24)
    window_end = ctx.cycle_end
    candidates: list[Action] = [
        Stop(reason=StoppingReason.NEGATIVE_EXPECTED_VALUE),
        EscalateToHuman(reason="no positive-expected-value action found this cycle"),
    ]

    day = window_start.replace(hour=DEBIT_HOUR, minute=0, second=0, microsecond=0)
    if day < window_start:
        day += timedelta(days=1)

    while day <= window_end:
        for channel in Channel:
            notice = SendPreDebitNotice(
                t=day - timedelta(hours=24), channel=channel, template_id=TEMPLATE_PDN
            )
            candidates.append(
                ScheduleDebit(t=day, notice=notice, afa_confirmed=ctx.afa_threshold_applicable)
            )
        if ctx.has_declared_preferred_day and ctx.declared_preferred_day is not None:
            candidates.append(
                OfferDateChange(
                    t=day,
                    channel=Channel.WHATSAPP,
                    template_id=TEMPLATE_DATE_CHANGE,
                    new_preferred_day=ctx.declared_preferred_day,
                )
            )
        day += timedelta(days=1)

    return candidates


@dataclass(frozen=True)
class _Score:
    expected_net: Money
    band_lo: Money
    band_hi: Money
    rupee_math: RupeeMath
    feature_attribution: dict[str, float]


_ZERO_MATH = RupeeMath(
    p_success=0.0, amount=0.0, p_revoke=0.0, ltv_remaining=0.0, cost=0.0, expected_net=0.0
)
_ZERO_SCORE = _Score(
    expected_net=0.0, band_lo=0.0, band_hi=0.0, rupee_math=_ZERO_MATH, feature_attribution={}
)


def _score_all(candidates: list[Action], ctx: DecisionContext, models: ModelBundle) -> list[_Score]:
    """Scores every candidate with **one** `predict_lgbm`/`predict_lgbm_contrib`/`predict`
    call each per `decide()` invocation, not one call per candidate.

    Two invariance facts make this a pure vectorization, not a behavior change (locked in
    by `tests/test_agent_decide_characterization.py`, which uses fakes whose predictions
    vary per row specifically to catch a row-misalignment bug this refactor could
    introduce):

    - `_hazard_row(ctx)` depends only on `ctx`, never on a candidate's proposed time `t` —
      every `ScheduleDebit` candidate in a single `decide()` call was already getting an
      *identical* hazard prediction before this refactor, just recomputed ~30 times.
      Computed once here and reused. Same for the bank-health as-of lookup
      (`_latest_bank_health`), which is also `ctx`-only.
    - `_recovery_row(ctx, t, ...)` depends on the candidate's day `t` but not its
      `Channel` (channel only affects `cost`, looked up separately per candidate) — three
      `ScheduleDebit` candidates a day apart in `t` shared identical recovery rows before
      this refactor too. Batched here into one `predict_lgbm`/`predict_lgbm_contrib` call
      over the unique days, keyed back per candidate by `t`.
    """
    schedule_debits = [a for a in candidates if isinstance(a, ScheduleDebit)]

    p_revoke = 0.0
    n_recovery = 0
    n_hazard = 0
    p_success_by_day: dict[Any, float] = {}
    contrib_by_day: dict[Any, list[float]] = {}
    if schedule_debits:
        bank_ewma, bank_changepoint = _latest_bank_health(models, ctx)
        n_recovery = int(models.recovery_slices_by_bank.get(ctx.bank_id, {}).get("n", 0))
        n_hazard = int(models.hazard_slices_by_method.get(ctx.method, {}).get("n", 0))

        days: list[Any] = []
        seen_days: set[Any] = set()
        for debit in schedule_debits:
            if debit.t not in seen_days:
                seen_days.add(debit.t)
                days.append(debit.t)

        recovery_rows = pd.concat(
            [_recovery_row(ctx, t, bank_ewma, bank_changepoint) for t in days], ignore_index=True
        )
        p_success_arr = models.recovery.predict_lgbm(recovery_rows)
        contrib_arr = models.recovery.predict_lgbm_contrib(recovery_rows)
        p_success_by_day = {t: float(p) for t, p in zip(days, p_success_arr, strict=True)}
        contrib_by_day = {
            t: [float(c) for c in row] for t, row in zip(days, contrib_arr, strict=True)
        }

        p_revoke = float(models.hazard.predict(_hazard_row(ctx))[0])

    ltv = ltv_remaining(
        ctx.amount, models.life_table, ctx.merchant_category, ctx.cycle_index - 1, models.sim_params
    )

    scores: list[_Score] = []
    for action in candidates:
        if isinstance(action, Stop | EscalateToHuman):
            scores.append(_ZERO_SCORE)
        elif isinstance(action, ScheduleDebit):
            channel = action.notice.channel.value
            cost = float(models.sim_params.get(f"notification.cost_inr.{channel}"))
            scores.append(
                _net_score(
                    p_success_by_day[action.t],
                    p_revoke,
                    ctx.amount,
                    ltv,
                    cost,
                    contrib_by_day[action.t],
                    n_recovery,
                    n_hazard,
                )
            )
        elif isinstance(action, OfferDateChange):
            scores.append(_score_offer_date_change(action, ctx, models))
        else:
            raise TypeError(f"no scoring rule for {type(action).__name__}")  # pragma: no cover
    return scores


def _score_offer_date_change(
    action: OfferDateChange, ctx: DecisionContext, models: ModelBundle
) -> _Score:
    del action
    # A date-change offer's value is the avoided future failure-and-hazard cost of a
    # mistimed debit day, not this cycle's own P(success)/P(revoke) — that comparison
    # needs the eval harness's response-rate mechanic (docs/07-EVAL-SPEC.md), which is
    # Phase 4. Scored flat at a small fixed positive value here so it survives the
    # compliance gate and appears in the audit trail as a considered, gated, but not yet
    # numerically-modelled alternative — never silently dropped, never overclaimed.
    return _Score(
        expected_net=0.01,
        band_lo=0.01,
        band_hi=0.01,
        rupee_math=RupeeMath(
            p_success=0.0,
            amount=ctx.amount,
            p_revoke=0.0,
            ltv_remaining=0.0,
            cost=0.0,
            expected_net=0.01,
        ),
        feature_attribution={},
    )


def _net_score(
    p_success: float,
    p_revoke: float,
    amount: Money,
    ltv: Money,
    cost: Money,
    contrib: list[float],
    n_recovery: int,
    n_hazard: int,
) -> _Score:
    expected_net = p_success * amount - p_revoke * ltv - cost

    p_success_lo, p_success_hi = _wilson_interval(p_success, n_recovery)
    p_revoke_lo, p_revoke_hi = _wilson_interval(p_revoke, n_hazard)

    band_lo = p_success_lo * amount - p_revoke_hi * ltv - cost
    band_hi = p_success_hi * amount - p_revoke_lo * ltv - cost

    feature_attribution = dict(
        zip(RECOVERY_FEATURE_COLUMNS, [float(c) for c in contrib[:-1]], strict=True)
    )

    return _Score(
        expected_net=expected_net,
        band_lo=band_lo,
        band_hi=band_hi,
        rupee_math=RupeeMath(
            p_success=p_success,
            amount=amount,
            p_revoke=p_revoke,
            ltv_remaining=ltv,
            cost=cost,
            expected_net=expected_net,
        ),
        feature_attribution=feature_attribution,
    )


def _wilson_interval(p: float, n: int) -> tuple[float, float]:
    """Wilson score interval on a binomial proportion, not the normal approximation
    (`p +/- z*sqrt(p*(1-p)/n)`) it replaced. The normal approximation undercovers at
    small `n` and near `p` = 0 or 1 — exactly the thin-slice, low-hazard regime this band
    is checked against for `ABSTAIN` — and can fall outside `[0, 1]` there, which a
    probability band never should. Wilson is bounded to `[0, 1]` by construction and
    well-behaved at small `n`. See docs/DECISIONS.md [2026-08-25].
    """
    if n <= 0:
        return 0.0, 1.0
    z2 = Z_95 * Z_95
    denom = 1 + z2 / n
    center = (p + z2 / (2 * n)) / denom
    margin = (Z_95 / denom) * math.sqrt(p * (1 - p) / n + z2 / (4 * n * n))
    return max(0.0, center - margin), min(1.0, center + margin)


def _recovery_row(
    ctx: DecisionContext, t: pd.Timestamp, bank_health_ewma: float, bank_health_changepoint: bool
) -> pd.DataFrame:
    hours_since_last = (
        (t - ctx.last_attempt_at).total_seconds() / 3600
        if ctx.last_attempt_at is not None
        else float("nan")
    )
    rate_to_date = (
        ctx.n_successes_to_date / ctx.n_attempts_to_date if ctx.n_attempts_to_date else float("nan")
    )
    days_from_declared = (
        abs(ctx.cycle_due_date.day - ctx.declared_preferred_day)
        if ctx.has_declared_preferred_day and ctx.declared_preferred_day is not None
        else float("nan")
    )
    days_until_cycle_end = CYCLE_LENGTH_DAYS - (t - ctx.cycle_due_date).days

    row: dict[str, Any] = {
        "bank_id": ctx.bank_id,
        "bank_health_ewma": bank_health_ewma,
        "bank_health_changepoint": bank_health_changepoint,
        "bank_dow_profile": t.weekday(),
        "is_bank_holiday": t.weekday() == 6,
        "method": ctx.method,
        "method_x_bank_success_rate": rate_to_date,
        "attempt_index": ctx.attempt_index,
        "hours_since_last_attempt": hours_since_last,
        "prior_failures_this_cycle": ctx.prior_failures_this_cycle,
        "consecutive_failed_cycles": ctx.consecutive_failed_cycles,
        "mandate_success_rate_to_date": rate_to_date,
        "mandate_age_cycles": ctx.cycle_index - 1,
        "day_of_month": t.day,
        "is_month_start_window": t.day <= 5,
        "is_mid_month_window": 10 <= t.day <= 20,
        "day_of_week": t.weekday(),
        "days_until_cycle_end": days_until_cycle_end,
        "amount": ctx.amount,
        "amount_vs_afa_threshold": ctx.amount / AFA_THRESHOLD_INR,
        "amount_vs_mandate_typical": 1.0,
        "prev_error_source": ctx.prev_error_source,
        "prev_error_step": ctx.prev_error_step,
        "prev_error_reason": ctx.prev_error_reason,
        "has_declared_preferred_day": ctx.has_declared_preferred_day,
        "days_from_declared_day": days_from_declared,
    }
    return pd.DataFrame([row], columns=RECOVERY_FEATURE_COLUMNS)


def _hazard_row(ctx: DecisionContext) -> pd.DataFrame:
    row: dict[str, Any] = {
        "failure_notifications_this_cycle": ctx.failure_notifications_this_cycle,
        "total_contacts_30d": ctx.total_contacts_30d,
        "days_since_first_failure_this_cycle": ctx.days_since_first_failure_this_cycle,
        "consecutive_failed_cycles": ctx.consecutive_failed_cycles,
        "mandate_age_cycles": ctx.cycle_index - 1,
        "amount_band": amount_band(ctx.amount),
        "method": ctx.method,
        "merchant_category": ctx.merchant_category,
        "has_customer_engaged_with_notice": ctx.has_customer_engaged_with_notice,
    }
    return pd.DataFrame([row], columns=HAZARD_FEATURE_COLUMNS)


def _abstention_reason(
    ctx: DecisionContext, models: ModelBundle, config: PolicyConfig, best: _Score
) -> AbstentionReason | None:
    min_slice_n = int(config.get("min_slice_n"))
    bank_slice = models.recovery_slices_by_bank.get(ctx.bank_id)
    if bank_slice is None or int(bank_slice.get("n", 0)) < min_slice_n:
        return AbstentionReason.INSUFFICIENT_SLICE_N

    _, changepoint = _latest_bank_health(models, ctx)
    if changepoint:
        return AbstentionReason.BANK_HEALTH_CHANGEPOINT

    max_brier = float(config.get("max_slice_brier"))
    bank_brier = bank_slice.get("brier_score", {}).get("point")
    if bank_brier is not None and bank_brier > max_brier:
        return AbstentionReason.SLICE_CALIBRATION_ERROR
    method_slice = models.hazard_slices_by_method.get(ctx.method, {})
    method_brier = method_slice.get("brier_score", {}).get("point")
    if method_brier is not None and method_brier > max_brier:
        return AbstentionReason.SLICE_CALIBRATION_ERROR

    if best.band_lo < 0 < best.band_hi:
        return AbstentionReason.EXPECTED_VALUE_CI_STRADDLES_ZERO

    return None


def _latest_bank_health(models: ModelBundle, ctx: DecisionContext) -> tuple[float, bool]:
    """As-of join (strictly before `ctx.now`), mirroring
    `features/recovery.py::build_recovery_features`'s bank-health join. Returns
    `(ewma_success, changepoint_flag)`, `(nan, False)` when no snapshot yet exists.
    """
    snaps = models.bank_health
    matching = snaps[
        (snaps["bank_id"] == ctx.bank_id)
        & (snaps["method"] == ctx.method)
        & (snaps["as_of"] < ctx.now)
    ]
    if matching.empty:
        return float("nan"), False
    latest = matching.iloc[-1]
    return float(latest["ewma_success"]), bool(latest["changepoint_flag"])


def _describe(action: Action) -> str:
    if isinstance(action, ScheduleDebit):
        return f"retry {action.t.isoformat()} via {action.notice.channel.value}"
    if isinstance(action, OfferDateChange):
        return f"offer date change to day {action.new_preferred_day} at {action.t.isoformat()}"
    if isinstance(action, Stop):
        return f"stop ({action.reason.value})"
    if isinstance(action, EscalateToHuman):
        return f"escalate ({action.reason})"
    return type(action).__name__  # pragma: no cover


def _reject_reason(candidate: _Score, best: _Score) -> str:
    delta = best.expected_net - candidate.expected_net
    return f"E[net] lower by Rs.{delta:.2f} than the chosen candidate"
