"""Tests for `agent/decide.py` — the pure decision function. Uses fake, hand-built
`ModelBundle`/`PolicyConfig` objects rather than trained artifacts: compliance,
candidate-generation, abstention and purity behaviour don't depend on real model
weights, and keeping this suite off the `make train` pipeline keeps it fast (this
matters especially for the `hypothesis` property test below, which calls `decide()`
hundreds of times).
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pandas as pd
from hypothesis import given, settings
from hypothesis import strategies as st

from agent.actions import Abstain, EscalateToHuman, OfferDateChange, ScheduleDebit, Stop
from agent.audit import AuditTrail, render
from agent.compliance import Severity, evaluate
from agent.context import DecisionContext
from agent.decide import _generate_candidates, decide
from agent.models import ModelBundle
from agent.stopping import StoppingReason
from features.recovery import RECOVERY_FEATURE_COLUMNS
from models.ltv import LifeTable
from sim.params import Params


class _FakeRecoveryModel:
    model_version = "fake_recovery_v1"

    def __init__(self, p_success: float = 0.6) -> None:
        self.p_success = p_success

    def predict_lgbm(self, df: pd.DataFrame) -> list[float]:
        return [self.p_success] * len(df)

    def predict_lgbm_contrib(self, df: pd.DataFrame) -> list[list[float]]:
        # len(RECOVERY_FEATURE_COLUMNS) features + 1 trailing bias term (LightGBM's
        # `pred_contrib` convention) — see RECOVERY_FEATURE_COLUMNS import below.
        return [[0.0] * (len(RECOVERY_FEATURE_COLUMNS) + 1) for _ in range(len(df))]


class _FakeHazardModel:
    model_version = "fake_hazard_v1"

    def __init__(self, p_revoke: float = 0.02) -> None:
        self.p_revoke = p_revoke

    def predict(self, df: pd.DataFrame) -> list[float]:
        return [self.p_revoke] * len(df)


def _params(raw: dict[str, object]) -> Params:
    return Params(raw=raw)


def _sim_params() -> Params:
    return _params(
        {
            "notification": {
                "cost_inr": {
                    "sms": {"value": 0.15},
                    "whatsapp": {"value": 0.35},
                    "push": {"value": 0.0},
                }
            },
            "ltv": {"margin_factor": {"value": 0.7}, "horizon_cycles": {"value": 8}},
        }
    )


def _policy_config(**overrides: object) -> Params:
    raw = {
        "max_attempts_per_cycle": {"value": 3},
        "max_notifications_per_cycle": {"value": 3},
        "cost_cap_inr": {"value": 5.0},
        "human_signoff_threshold_inr": {"value": 15000},
        "min_slice_n": {"value": 30},
        "holdout_fraction": {"value": 0.1},
        "retry_requires_fresh_pdn": {"value": True},
        "converge_min_cycles_between_date_changes": {"value": 4},
    }
    for k, v in overrides.items():
        raw[k] = {"value": v}
    return _params(raw)


def _life_table() -> LifeTable:
    survival = {("ott", age): max(0.0, 1.0 - 0.05 * age) for age in range(0, 9)}
    return LifeTable(survival=survival, horizon_cycles=8)


def _bank_health(changepoint: bool = False) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "bank_id": "HDFC",
                "method": "upi_autopay",
                "as_of": datetime(2026, 8, 1),
                "ewma_success": 0.9,
                "decay_rate": 0.1,
                "changepoint_flag": changepoint,
                "sample_n": 500,
            }
        ]
    )


def _fake_bundle(
    p_success: float = 0.6,
    p_revoke: float = 0.02,
    slice_n: int = 500,
    slice_brier: float = 0.12,
    slice_bss: float = 0.4,
    changepoint: bool = False,
) -> ModelBundle:
    slice_block = {
        "n": slice_n,
        "brier_score": {"point": slice_brier},
        "brier_skill_score": slice_bss,
    }
    return ModelBundle(
        recovery=_FakeRecoveryModel(p_success),  # type: ignore[arg-type]
        hazard=_FakeHazardModel(p_revoke),  # type: ignore[arg-type]
        life_table=_life_table(),
        sim_params=_sim_params(),
        recovery_slices_by_bank={"HDFC": slice_block},
        hazard_slices_by_method={"upi_autopay": slice_block},
        bank_health=_bank_health(changepoint),
    )


def _base_ctx(**overrides: object) -> DecisionContext:
    defaults: dict[str, object] = dict(
        mandate_id=8813,
        cycle_id=1,
        cycle_index=6,
        merchant_category="ott",
        bank_id="HDFC",
        method="upi_autopay",
        amount=499.0,
        afa_threshold_applicable=False,
        now=datetime(2026, 8, 28, 9, 14, 2),
        cycle_due_date=datetime(2026, 8, 1),
        cycle_end=datetime(2026, 9, 5),
        attempt_index=2,
        last_attempt_at=datetime(2026, 8, 27, 10, 0),
        last_attempt_outcome="soft_decline",
        n_attempts_to_date=1,
        n_successes_to_date=0,
        prior_failures_this_cycle=1,
        consecutive_failed_cycles=0,
        prev_error_source="customer",
        prev_error_step="payment_authorization",
        prev_error_reason="insufficient_funds",
        failure_notifications_this_cycle=1,
        total_contacts_30d=1,
        days_since_first_failure_this_cycle=1,
        has_customer_engaged_with_notice=False,
        notifications_sent_this_cycle=1,
        notification_cost_spent_this_cycle_inr=0.15,
        last_pdn_sent_at=datetime(2026, 8, 27, 9, 0),
        has_declared_preferred_day=False,
        declared_preferred_day=None,
        date_change_last_offered_cycle_index=None,
        customer_opted_out=False,
        mandate_revoked=False,
    )
    defaults.update(overrides)
    return DecisionContext(**defaults)  # type: ignore[arg-type]


def test_purity_same_inputs_same_output() -> None:
    ctx = _base_ctx()
    models = _fake_bundle()
    config = _policy_config()
    d1 = decide(ctx, models, config)
    d2 = decide(ctx, models, config)
    assert d1 == d2


def test_hard_decline_stops() -> None:
    ctx = _base_ctx(last_attempt_outcome="hard_decline")
    d = decide(ctx, _fake_bundle(), _policy_config())
    assert d.chosen == Stop(reason=StoppingReason.HARD_DECLINE)
    assert d.stopping_reason == StoppingReason.HARD_DECLINE


def test_mandate_revoked_stops() -> None:
    ctx = _base_ctx(mandate_revoked=True)
    d = decide(ctx, _fake_bundle(), _policy_config())
    assert d.chosen == Stop(reason=StoppingReason.MANDATE_REVOKED)


def test_customer_opted_out_stops() -> None:
    ctx = _base_ctx(customer_opted_out=True)
    d = decide(ctx, _fake_bundle(), _policy_config())
    assert d.chosen == Stop(reason=StoppingReason.CUSTOMER_OPTED_OUT)


def test_max_attempts_stops() -> None:
    ctx = _base_ctx(attempt_index=4)
    d = decide(ctx, _fake_bundle(), _policy_config(max_attempts_per_cycle=3))
    assert d.chosen == Stop(reason=StoppingReason.MAX_ATTEMPTS)


def test_cost_cap_stops() -> None:
    ctx = _base_ctx(notification_cost_spent_this_cycle_inr=10.0)
    d = decide(ctx, _fake_bundle(), _policy_config(cost_cap_inr=5.0))
    assert d.chosen == Stop(reason=StoppingReason.COST_CAP)


def test_negative_expected_value_stops_when_hazard_dominates() -> None:
    ctx = _base_ctx()
    models = _fake_bundle(p_success=0.05, p_revoke=0.9)
    d = decide(ctx, models, _policy_config())
    assert d.chosen == Stop(reason=StoppingReason.NEGATIVE_EXPECTED_VALUE)
    assert d.expected_net <= 0


def test_positive_expected_value_schedules_a_debit() -> None:
    ctx = _base_ctx()
    models = _fake_bundle(p_success=0.9, p_revoke=0.01, slice_n=5000)
    d = decide(ctx, models, _policy_config())
    assert isinstance(d.chosen, ScheduleDebit)
    assert d.stopping_reason is None
    assert d.expected_net > 0
    assert len(d.rejected_alternatives) > 0


def test_tie_break_prefers_earliest_date_with_no_declared_preference() -> None:
    # A constant-output fake model ties every ScheduleDebit candidate's E[net] exactly
    # (same p_success/p_revoke/cost regardless of day) -- this is the real, common case
    # documented in agent/decide.py's `_tie_break_score`, not a contrived edge case.
    # window_start = now + 24h = 2026-08-29 09:14:02 -> first legal debit day 08-29.
    ctx = _base_ctx(has_declared_preferred_day=False, declared_preferred_day=None)
    models = _fake_bundle(p_success=0.9, p_revoke=0.01, slice_n=5000)
    d = decide(ctx, models, _policy_config())
    assert isinstance(d.chosen, ScheduleDebit)
    assert d.chosen.t == datetime(2026, 8, 29, 10, 0)
    # the tie collapses into one summary entry, not one near-duplicate per tied day
    tie_summaries = [a for a in d.rejected_alternatives if a.reason.startswith("not chosen:")]
    assert len(tie_summaries) == 1
    assert "earliest available date" in tie_summaries[0].reason


def test_tie_break_prefers_closest_to_declared_day() -> None:
    # Same tie, but with a declared preferred day (Sept 2) -- restraint should now
    # resolve toward the customer's own stated preference instead of the earliest date.
    ctx = _base_ctx(has_declared_preferred_day=True, declared_preferred_day=2)
    models = _fake_bundle(p_success=0.9, p_revoke=0.01, slice_n=5000)
    d = decide(ctx, models, _policy_config())
    assert isinstance(d.chosen, ScheduleDebit)
    assert d.chosen.t == datetime(2026, 9, 2, 10, 0)
    tie_summaries = [a for a in d.rejected_alternatives if a.reason.startswith("not chosen:")]
    assert len(tie_summaries) == 1
    assert "closest to the customer's declared preferred day (day 2)" in tie_summaries[0].reason


def test_abstains_on_insufficient_slice_n() -> None:
    ctx = _base_ctx()
    models = _fake_bundle(p_success=0.9, p_revoke=0.01, slice_n=5)
    d = decide(ctx, models, _policy_config(min_slice_n=30))
    assert isinstance(d.chosen, Abstain)
    assert d.chosen.reason.value == "insufficient_slice_n"
    assert d.stopping_reason == StoppingReason.INSUFFICIENT_CONFIDENCE


def test_abstains_on_bank_health_changepoint() -> None:
    ctx = _base_ctx()
    models = _fake_bundle(p_success=0.9, p_revoke=0.01, slice_n=5000, changepoint=True)
    d = decide(ctx, models, _policy_config())
    assert isinstance(d.chosen, Abstain)
    assert d.chosen.reason.value == "bank_health_changepoint"


def test_abstains_on_slice_calibration_error() -> None:
    ctx = _base_ctx()
    models = _fake_bundle(p_success=0.9, p_revoke=0.01, slice_n=5000, slice_bss=-0.1)
    d = decide(ctx, models, _policy_config())
    assert isinstance(d.chosen, Abstain)
    assert d.chosen.reason.value == "slice_calibration_error"


def test_abstains_when_ci_straddles_zero() -> None:
    # A thin-but-not-insufficient slice (n == min_slice_n, so the slice-size trigger
    # itself does not fire) widens the proportion-CI enough that the low end of E[net]
    # goes negative while the point estimate stays positive.
    ctx = _base_ctx()
    models = _fake_bundle(p_success=0.3, p_revoke=0.1, slice_n=30, slice_brier=0.1)
    d = decide(ctx, models, _policy_config(min_slice_n=30))
    assert isinstance(d.chosen, Abstain)
    assert d.chosen.reason.value == "expected_value_ci_straddles_zero"


def test_offer_date_change_is_a_gated_candidate_when_declared() -> None:
    ctx = _base_ctx(has_declared_preferred_day=True, declared_preferred_day=5)
    models = _fake_bundle(p_success=0.01, p_revoke=0.5, slice_n=5000)  # tank the debit score
    d = decide(ctx, models, _policy_config())
    descriptions = [alt.description for alt in d.rejected_alternatives]
    if not isinstance(d.chosen, OfferDateChange):
        assert any("offer date change" in desc for desc in descriptions)


def test_offer_date_change_too_soon_is_logged_as_a_soft_violation_not_excluded() -> None:
    # DOBARA-CONVERGE is SOFT (docs/01-REGULATORY.md) — a too-soon offer is not excluded
    # from the candidate pool by `is_hard_compliant`, only flagged in `clauses_blocked` if
    # it happens to win. "SOFT-rule violations do not disqualify"
    # (agent/compliance.py::is_hard_compliant).
    ctx = _base_ctx(
        has_declared_preferred_day=True,
        declared_preferred_day=5,
        date_change_last_offered_cycle_index=5,
        cycle_index=6,
    )
    config = _policy_config(converge_min_cycles_between_date_changes=4)
    # Tank the debit score so OfferDateChange (flat 0.01) is the only positive candidate.
    models = _fake_bundle(p_success=0.01, p_revoke=0.5, slice_n=5000)
    d = decide(ctx, models, config)
    assert isinstance(d.chosen, OfferDateChange)
    assert any(c.id == "DOBARA-CONVERGE" for c in d.clauses_blocked)


def test_afa_gate_blocks_unconfirmed_high_value_debit() -> None:
    ctx = _base_ctx(amount=20000.0, afa_threshold_applicable=False)
    models = _fake_bundle(p_success=0.99, p_revoke=0.001, slice_n=5000)
    d = decide(ctx, models, _policy_config())
    assert not isinstance(d.chosen, ScheduleDebit)


def test_requires_signoff_above_threshold() -> None:
    ctx = _base_ctx(amount=20000.0, afa_threshold_applicable=True)
    models = _fake_bundle(p_success=0.99, p_revoke=0.001, slice_n=5000)
    d = decide(ctx, models, _policy_config(human_signoff_threshold_inr=15000))
    assert d.requires_signoff


def test_escalate_to_human_is_always_a_considered_candidate() -> None:
    # Checked against candidate generation directly, not the audit trail's textual
    # description: EscalateToHuman ties with Stop at the E[net]=0.0 baseline whenever
    # neither wins outright, and agent/decide.py's tie-collapsing (docs/DECISIONS.md
    # [2026-08-27]) folds that pair into one summary line rather than naming it --
    # "always considered" is a candidate-generation invariant, not a display one.
    ctx = _base_ctx()
    candidates = _generate_candidates(ctx, _policy_config())
    assert any(isinstance(c, EscalateToHuman) for c in candidates)


def test_rupee_math_carries_every_term() -> None:
    ctx = _base_ctx()
    models = _fake_bundle(p_success=0.9, p_revoke=0.01, slice_n=5000)
    d = decide(ctx, models, _policy_config())
    rm = d.rupee_math
    assert rm.expected_net == rm.p_success * rm.amount - rm.p_revoke * rm.ltv_remaining - rm.cost


def test_audit_trail_is_append_only_and_renders() -> None:
    trail = AuditTrail()
    ctx = _base_ctx()
    models = _fake_bundle(p_success=0.9, p_revoke=0.01, slice_n=5000)
    d = decide(ctx, models, _policy_config())
    record = trail.append(ctx, d)
    assert trail.records() == (record,)

    text = render(record)
    for section in ("SAW", "THOUGHT", "ALT", "GATE", "DID", "WHY"):
        assert f"  {section}" in text or text.startswith(section)

    trail.append(ctx, d)
    assert len(trail.records()) == 2
    assert trail.records()[0] == record  # first entry never mutated by the second append


@st.composite
def _hypothesis_ctx(draw: st.DrawFn) -> DecisionContext:
    now = draw(st.datetimes(min_value=datetime(2026, 1, 1), max_value=datetime(2026, 12, 1)))
    amount = draw(st.floats(min_value=50.0, max_value=150_000.0, allow_nan=False))
    attempt_index = draw(st.integers(min_value=1, max_value=6))
    notifications_sent = draw(st.integers(min_value=0, max_value=4))
    afa_confirmed = draw(st.booleans())
    has_declared = draw(st.booleans())
    declared_day = draw(st.integers(min_value=1, max_value=28)) if has_declared else None
    return _base_ctx(
        now=now,
        cycle_due_date=now - timedelta(days=draw(st.integers(min_value=0, max_value=20))),
        cycle_end=now + timedelta(days=draw(st.integers(min_value=1, max_value=25))),
        amount=amount,
        afa_threshold_applicable=afa_confirmed,
        attempt_index=attempt_index,
        notifications_sent_this_cycle=notifications_sent,
        has_declared_preferred_day=has_declared,
        declared_preferred_day=declared_day,
    )


@given(ctx=_hypothesis_ctx())
@settings(max_examples=200, deadline=None)
def test_decide_never_returns_an_action_violating_a_hard_rule(ctx: DecisionContext) -> None:
    models = _fake_bundle()
    config = _policy_config()
    decision = decide(ctx, models, config)
    _, blocked = evaluate(decision.chosen, ctx, config)
    hard_violations = [r for r in blocked if r.severity == Severity.HARD]
    assert not hard_violations, (
        f"decide() returned {decision.chosen!r} which violates HARD rule(s) "
        f"{[r.id for r in hard_violations]} for ctx={ctx!r}"
    )
