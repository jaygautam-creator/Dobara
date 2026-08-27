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
comes from `models.recovery` (Model 1, `models/recovery.py`).

**`P(revoke)` is NOT the hazard model's raw output — it must be weighted by `P(fail)`,
and getting this wrong is a real bug we found and fixed (2026-08-25).**
`models/hazard.py`'s exposure unit is "one row per `soft_decline` attempt"
(`features/hazard.py`'s docstring): the model is trained on, and therefore predicts,
`P(revoke | this attempt already failed)` — a *conditional* probability. But `decide()`
scores a candidate *before* its outcome is known, including a cycle's very first
attempt, when no failure has happened yet. Using the model's raw output directly as the
unconditional `P(revoke)` this formula needs silently substitutes `P(revoke | fail)` for
`P(revoke)`, which — since `P(revoke) = P(fail) * P(revoke | fail)` and `P(fail) < 1` —
overstates every candidate's downside by a factor of `1/P(fail)`. The fix:
`p_revoke = (1 - p_success) * hazard_raw`, computed per candidate (since `p_success`
varies by day `t`, `hazard_raw` does not — see `_score_all`'s docstring). This also
corrected `docs/06-AGENT-SPEC.md`'s own worked audit-trail example, which had the same
unweighted form. See `docs/DECISIONS.md` [2026-08-25] "Fixed: P(revoke) was the hazard
model's raw conditional-on-failure output, not the unconditional probability the E[net]
formula needs" for the full diagnosis (discovered via `dobara` underperforming
`do_nothing` net LTV in Phase 4's eval harness — inflated `P(revoke)` was pushing
`decide()` away from real `ScheduleDebit` retries toward `OfferDateChange`'s unmodelled
flat placeholder score, which still costs a notification for no realized recovery).

Separately, **`hazard_per_failure_notification` is a declared assumption in
`sim/params.yaml`, recalibrated 2026-08-25; the hazard model's prediction here is only as
trustworthy as that assumption, which is exactly why `min_slice_n`/slice-Brier-skill/
change-point abstention exists below rather than trusting every prediction blindly** (see
`docs/DECISIONS.md` [2026-08-25] "Corrected: the hazard headline number does not confirm
the thesis"). `LTV_remaining` comes from `models.life_table` (`models/ltv.py`, a
transparent life-table estimate, not a model prediction). `cost` is read from
`sim/params.yaml`'s `notification.cost_inr.*`.

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
- Slice calibration error: a Brier Skill Score `<= 0` (no better than predicting the
  slice's own held-out marginal rate) against the hazard method-slice only, re-derived
  2026-08-26 from `models/metrics.py::metric_block`'s `brier_climatology` (see
  docs/DECISIONS.md [2026-08-26] "Step 2" — was a hand-picked `config.max_slice_brier`
  constant before this). **The recovery model's per-bank Brier score is
  deliberately NOT checked here anymore** (removed 2026-08-25) — it is a single number
  measured once at training time on the test-split cycles (6-8), so for a bank whose
  test-window calibration happened to be bad (the regime-shift bank, by design), the
  check fired on *every* decision for that bank for its *entire* mandate life, cycles 1-5
  included, where nothing was actually wrong. A static, time-unaware number cannot tell
  "this bank in general" from "this bank right now" — exactly the job the change-point
  detector above already does, correctly, with real temporal granularity, once it was
  recalibrated (see `docs/DECISIONS.md` [2026-08-25] "`bank_health_changepoint` detector
  recalibrated"). Keeping both was strictly worse than the change-point detector alone:
  the static check could only ever produce false positives it couldn't tell were false.
  See `docs/DECISIONS.md` [2026-08-25] "Static per-bank Brier abstention check removed".
- The confidence band on the winning real action's `E[net]` straddling zero.

On any trigger the chosen action becomes `Abstain(reason)`; the caller must not attempt
this cycle when it sees `Abstain` (per CLAUDE.md: "when in doubt, the agent stops" — see
docs/DECISIONS.md [2026-08-25] "Abstain must stop, not fall back to an attempt", which
overrules this module's earlier fall-back-to-the-default-policy design). `agent/audit.py`'s
renderer states this in the human-readable line — `decide()` itself only names *why*, per
the pure-function/no-I/O boundary.
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
    scored.sort(
        key=lambda pair: (pair[1].expected_net, -_tie_break_score(pair[0], ctx)), reverse=True
    )

    best_action, best = scored[0]
    rejected = _rejected_alternatives(best_action, best, scored[1:], ctx)

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


def _tie_break_score(action: Action, ctx: DecisionContext) -> float:
    """Breaks ties in `E[net]` — and these are real, not rare: on the committed demo
    fixture, 76% of decisions with alternatives have an exact tie at the top of the
    argmax, most spanning many different candidate dates (see `docs/DECISIONS.md`
    [2026-08-27] for the full diagnosis — genuine day-of-month/day-of-week recovery
    signal exists and the trained model learns it, but the isotonic probability
    calibrator's small number of distinct output steps quantizes many different raw
    predictions to the identical calibrated `p_success`, and identical `p_success` at
    identical cost is an identical `E[net]`). Before this, ties resolved to whichever
    candidate `_generate_candidates` happened to emit first — the earliest legal day, by
    accident of loop order, since day-then-channel is the generation order and Python's
    sort is stable. That accident is now an explicit, tested rule, and it gains a case it
    never handled: **restraint decides when the money model is indifferent.** Lower
    returned score is more preferred:

    - When the customer has a declared or evidenced-stable preferred day
      (`ctx.has_declared_preferred_day`), prefer the `ScheduleDebit` candidate whose
      calendar day is closest to it — nudging back toward the day they actually asked
      for, at zero cost in expected value, is strictly better than an arbitrary one.
    - Otherwise (including every `OfferDateChange` candidate, whose own `t` is when the
      *offer* is sent, not a proposed debit day the customer has any stake in), prefer
      the earliest legal `t` — resolving the cycle sooner bounds how many further
      attempts/notifications this mandate can still generate, which is the same
      fewest-notifications/lowest-burden principle applied to the one thing a
      single-decision tie-break can actually control.

    Candidates without a `t` (`Stop`/`EscalateToHuman`) return 0.0 — they never need this
    axis, since compliance/candidate-generation determines whether they win, not a value
    tie against a real action at the same `E[net]`.
    """
    if not isinstance(action, ScheduleDebit | OfferDateChange):
        return 0.0
    t = action.t
    if (
        isinstance(action, ScheduleDebit)
        and ctx.has_declared_preferred_day
        and ctx.declared_preferred_day is not None
    ):
        return float(abs(t.day - ctx.declared_preferred_day))
    return (t - ctx.now).total_seconds()


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
      every `ScheduleDebit` candidate in a single `decide()` call gets an *identical*
      `hazard_raw` (the model's raw `P(revoke | fail)`) computed once here and reused;
      the per-candidate unconditional `p_revoke = (1 - p_success) * hazard_raw` still
      varies per candidate because `p_success` does. Same one-shot treatment for the
      bank-health as-of lookup (`_latest_bank_health`), which is also `ctx`-only.
    - `_recovery_row(ctx, t, ...)` depends on the candidate's day `t` but not its
      `Channel` (channel only affects `cost`, looked up separately per candidate) — three
      `ScheduleDebit` candidates a day apart in `t` shared identical recovery rows before
      this refactor too. Batched here into one `predict_lgbm`/`predict_lgbm_contrib` call
      over the unique days, keyed back per candidate by `t`.
    """
    schedule_debits = [a for a in candidates if isinstance(a, ScheduleDebit)]

    hazard_raw = 0.0
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

        # Raw model output is P(revoke | this attempt fails) -- a conditional
        # probability (features/hazard.py's exposure unit is one row per soft_decline
        # attempt). _net_score converts it to the unconditional P(revoke) the E[net]
        # formula needs by weighting with (1 - p_success), per-candidate, since
        # p_success varies by day and hazard_raw does not. See module docstring
        # "## Scoring" and docs/DECISIONS.md [2026-08-25].
        hazard_raw = float(models.hazard.predict(_hazard_row(ctx))[0])

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
                    hazard_raw,
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
    hazard_raw: float,
    amount: Money,
    ltv: Money,
    cost: Money,
    contrib: list[float],
    n_recovery: int,
    n_hazard: int,
) -> _Score:
    """`hazard_raw` is the hazard model's raw `P(revoke | this attempt fails)`. The
    unconditional `P(revoke)` the E[net] formula needs is `(1 - p_success) * hazard_raw`
    (see module docstring "## Scoring") -- computed here, not passed in, so it is never
    accidentally used unweighted elsewhere.
    """
    p_revoke = (1 - p_success) * hazard_raw
    expected_net = p_success * amount - p_revoke * ltv - cost

    p_success_lo, p_success_hi = _wilson_interval(p_success, n_recovery)
    hazard_lo, hazard_hi = _wilson_interval(hazard_raw, n_hazard)

    # p_revoke = (1 - p_success) * hazard_raw is a product of two uncertain terms.
    # Worst case for p_revoke (used in band_lo, the pessimistic E[net]) pairs the
    # highest plausible hazard with the highest plausible (1 - p_success) -- i.e. the
    # *lowest* plausible p_success; best case (band_hi) is the mirror. This is the same
    # worst-case/best-case interval-arithmetic convention _net_score already used for
    # p_success alone before this fix.
    p_revoke_worst = (1 - p_success_lo) * hazard_hi
    p_revoke_best = (1 - p_success_hi) * hazard_lo

    band_lo = p_success_lo * amount - p_revoke_worst * ltv - cost
    band_hi = p_success_hi * amount - p_revoke_best * ltv - cost

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

    # No static per-bank recovery-slice Brier check here (removed 2026-08-25) — see the
    # module docstring's "## Abstention" section for why a training-time-static number is
    # the wrong tool and the change-point detector above already covers this concern with
    # real temporal granularity. The hazard method-slice check below was itself a
    # hand-picked constant (`config.max_slice_brier`) until 2026-08-26 — re-derived per
    # docs/DECISIONS.md [2026-08-26] "Step 2" as a Brier Skill Score against the slice's
    # own held-out climatology baseline (`models/metrics.py::metric_block`), so "poorly
    # calibrated" means "worse than predicting this slice's own marginal rate," not an
    # arbitrary number nobody re-derives when the model changes.
    method_slice = models.hazard_slices_by_method.get(ctx.method, {})
    method_bss = method_slice.get("brier_skill_score")
    if method_bss is not None and method_bss <= 0:
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


def _tie_break_reason_text(best_action: Action, ctx: DecisionContext) -> str:
    """Human-readable version of `_tie_break_score`'s rule, for the audit trail's
    collapsed tie summary (`_rejected_alternatives`) — names the actual reason the
    chosen candidate won a tie, rather than a manufactured "lower by Rs.0.00" that isn't
    a reason at all. See `_tie_break_score`'s docstring for the full diagnosis."""
    if (
        isinstance(best_action, ScheduleDebit)
        and ctx.has_declared_preferred_day
        and ctx.declared_preferred_day is not None
    ):
        return (
            f"closest to the customer's declared preferred day (day {ctx.declared_preferred_day})"
        )
    if isinstance(best_action, ScheduleDebit | OfferDateChange):
        return "earliest available date, all else equal"
    # Stop tying EscalateToHuman at the E[net]=0.0 baseline (both always present, per
    # module docstring "## Candidate generation") -- Stop wins because it's listed
    # first and Python's sort is stable, a documented, deliberate ordering, not this
    # function's own tie-break axis.
    return "first considered, all else equal"


def _rejected_alternatives(
    best_action: Action, best: _Score, rest: list[tuple[Action, _Score]], ctx: DecisionContext
) -> list[RejectedAlternative]:
    """Builds the audit trail's rejected-alternative list from every non-chosen scored
    candidate, collapsing **every** run of mutually-tied candidates into one summary
    entry — not just the ones tied with `best`. The calibrator-plateau tie
    (`_tie_break_score`'s docstring, `docs/DECISIONS.md` [2026-08-27]) produces one tie
    cluster *per channel* in practice (same day-spanning collapse, three times, once per
    `Channel`), not only at the very top: on the committed demo fixture, restricting this
    to just the winning value left the channel below the winner's still repeating "lower
    by Rs.0.15" 17+ times. `rest` is already sorted descending by the same key `scored`
    was, so every tied cluster is a contiguous run — grouped here by walking it once,
    not by re-sorting.
    """
    alternatives: list[RejectedAlternative] = []
    i = 0
    while i < len(rest):
        value = rest[i][1].expected_net
        j = i
        while j < len(rest) and rest[j][1].expected_net == value:
            j += 1
        group = rest[i:j]
        if len(group) == 1:
            action, score = group[0]
            alternatives.append(
                RejectedAlternative(
                    description=_describe(action),
                    expected_net=score.expected_net,
                    reason=_reject_reason(score, best),
                )
            )
        else:
            plural = "s" if len(group) != 1 else ""
            if value == best.expected_net:
                reason = f"not chosen: {_tie_break_reason_text(best_action, ctx)}"
            else:
                reason = (
                    f"E[net] lower by Rs.{best.expected_net - value:.2f} than the chosen candidate"
                )
            alternatives.append(
                RejectedAlternative(
                    description=f"{len(group)} candidate{plural} tied at this E[net]",
                    expected_net=value,
                    reason=reason,
                )
            )
        i = j
    return alternatives
