"""Direct tests of `agent/compliance.py`'s gate: each HARD rule must actually block a
*violating* candidate, not just tolerate one that already avoids the problem — the
`test_agent_decide.py` hypothesis test only proves `decide()`'s own careful candidate
construction stays compliant, which says nothing about whether the gate itself would
catch a bad candidate if one were ever constructed (a future refactor, a bug, an
attacker-controlled input downstream). These tests build violating `Action`s by hand.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from agent.actions import Channel, OfferDateChange, ScheduleDebit, SendPreDebitNotice
from agent.compliance import is_hard_compliant
from agent.context import DecisionContext
from sim.params import Params


def _policy_config(**overrides: object) -> Params:
    raw: dict[str, object] = {
        "max_attempts_per_cycle": {"value": 3},
        "max_notifications_per_cycle": {"value": 3},
        "cost_cap_inr": {"value": 5.0},
        "human_signoff_threshold_inr": {"value": 15000},
        "min_slice_n": {"value": 30},
        "max_slice_brier": {"value": 0.15},
        "holdout_fraction": {"value": 0.1},
        "retry_requires_fresh_pdn": {"value": True},
        "converge_min_cycles_between_date_changes": {"value": 4},
    }
    for k, v in overrides.items():
        raw[k] = {"value": v}
    return Params(raw=raw)


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


def _notice(
    t: datetime,
    channel: Channel = Channel.WHATSAPP,
    template_id: str = "tmpl_pdn_defer_v3",
) -> SendPreDebitNotice:
    return SendPreDebitNotice(t=t, channel=channel, template_id=template_id)


def test_rbi_pdn_24h_blocks_a_debit_with_a_late_notice() -> None:
    ctx = _base_ctx()
    config = _policy_config()
    t = datetime(2026, 9, 2, 10, 0)
    late_notice = _notice(t - timedelta(hours=2))  # far short of the required 24h
    action = ScheduleDebit(t=t, notice=late_notice, afa_confirmed=True)
    assert not is_hard_compliant(action, ctx, config)


def test_rbi_pdn_24h_allows_a_debit_with_exactly_24h_notice() -> None:
    ctx = _base_ctx()
    config = _policy_config()
    t = datetime(2026, 9, 2, 10, 0)
    ok_notice = _notice(t - timedelta(hours=24))
    action = ScheduleDebit(t=t, notice=ok_notice, afa_confirmed=True)
    assert is_hard_compliant(action, ctx, config)


def test_conduct_hours_blocks_a_notice_before_8am() -> None:
    ctx = _base_ctx()
    config = _policy_config()
    t = datetime(2026, 9, 2, 10, 0)
    early_notice = _notice(t - timedelta(hours=24))
    early_notice = SendPreDebitNotice(
        t=early_notice.t.replace(hour=6), channel=Channel.WHATSAPP, template_id="tmpl_pdn_defer_v3"
    )
    action = ScheduleDebit(t=t, notice=early_notice, afa_confirmed=True)
    assert not is_hard_compliant(action, ctx, config)


def test_conduct_hours_blocks_a_notice_after_7pm() -> None:
    ctx = _base_ctx()
    config = _policy_config()
    t = datetime(2026, 9, 2, 10, 0)
    late_evening_notice = SendPreDebitNotice(
        t=(t - timedelta(hours=24)).replace(hour=20),
        channel=Channel.WHATSAPP,
        template_id="tmpl_pdn_defer_v3",
    )
    action = ScheduleDebit(t=t, notice=late_evening_notice, afa_confirmed=True)
    assert not is_hard_compliant(action, ctx, config)


def test_trai_dlt_blocks_an_unapproved_sms_template() -> None:
    ctx = _base_ctx()
    config = _policy_config()
    t = datetime(2026, 9, 2, 10, 0)
    bad_notice = SendPreDebitNotice(
        t=t - timedelta(hours=24), channel=Channel.SMS, template_id="not_a_registered_template"
    )
    action = ScheduleDebit(t=t, notice=bad_notice, afa_confirmed=True)
    assert not is_hard_compliant(action, ctx, config)


def test_wa_utility_blocks_an_unapproved_whatsapp_template() -> None:
    ctx = _base_ctx()
    config = _policy_config()
    t = datetime(2026, 9, 2, 10, 0)
    bad_notice = SendPreDebitNotice(
        t=t - timedelta(hours=24), channel=Channel.WHATSAPP, template_id="freeform_message"
    )
    action = ScheduleDebit(t=t, notice=bad_notice, afa_confirmed=True)
    assert not is_hard_compliant(action, ctx, config)


def test_rbi_afa_15k_blocks_high_value_debit_without_confirmation() -> None:
    ctx = _base_ctx(amount=20000.0)
    config = _policy_config()
    t = datetime(2026, 9, 2, 10, 0)
    action = ScheduleDebit(t=t, notice=_notice(t - timedelta(hours=24)), afa_confirmed=False)
    assert not is_hard_compliant(action, ctx, config)


def test_rbi_afa_15k_allows_high_value_debit_with_confirmation() -> None:
    ctx = _base_ctx(amount=20000.0)
    config = _policy_config()
    t = datetime(2026, 9, 2, 10, 0)
    action = ScheduleDebit(t=t, notice=_notice(t - timedelta(hours=24)), afa_confirmed=True)
    assert is_hard_compliant(action, ctx, config)


def test_rbi_afa_15k_allows_sub_threshold_debit_without_confirmation() -> None:
    ctx = _base_ctx(amount=499.0)
    config = _policy_config()
    t = datetime(2026, 9, 2, 10, 0)
    action = ScheduleDebit(t=t, notice=_notice(t - timedelta(hours=24)), afa_confirmed=False)
    assert is_hard_compliant(action, ctx, config)


def test_dobara_fatigue_blocks_beyond_the_cap() -> None:
    ctx = _base_ctx(notifications_sent_this_cycle=3)
    config = _policy_config(max_notifications_per_cycle=3)
    t = datetime(2026, 9, 2, 10, 0)
    action = ScheduleDebit(t=t, notice=_notice(t - timedelta(hours=24)), afa_confirmed=True)
    assert not is_hard_compliant(action, ctx, config)


def test_dobara_fatigue_allows_up_to_the_cap() -> None:
    ctx = _base_ctx(notifications_sent_this_cycle=2)
    config = _policy_config(max_notifications_per_cycle=3)
    t = datetime(2026, 9, 2, 10, 0)
    action = ScheduleDebit(t=t, notice=_notice(t - timedelta(hours=24)), afa_confirmed=True)
    assert is_hard_compliant(action, ctx, config)


def test_dobara_converge_is_soft_and_does_not_block() -> None:
    # DOBARA-CONVERGE is SOFT severity — a too-soon date-change offer must fail
    # `evaluate()`'s clause check but must NOT be excluded by `is_hard_compliant`.
    ctx = _base_ctx(date_change_last_offered_cycle_index=5, cycle_index=6)
    config = _policy_config(converge_min_cycles_between_date_changes=4)
    t = datetime(2026, 9, 2, 10, 0)
    action = OfferDateChange(
        t=t, channel=Channel.WHATSAPP, template_id="tmpl_date_change_v1", new_preferred_day=5
    )
    assert is_hard_compliant(action, ctx, config)
