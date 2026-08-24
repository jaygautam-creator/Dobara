"""The simulator engine. `sim.run(params, seed) -> summary` generates the ground truth:
merchants, customers, mandates, cycles, attempts, notifications, revocations — into a
SQLite database. Uses `sim.latent` internally for the hidden balance/bank generators, but
writes only PSP-observable fields (`sim.schema`) to the database.

The retry loop implemented here is the **default policy** ("razorpay_default": bounded
retries, 24h+ gap, fresh PDN before every retry) used to produce the Phase-1/2 training
history. `agent/` (Phase 3) and `eval/` (Phase 4) reuse the pure outcome primitives below
(`attempt_outcome`, `revocation_hazard`) to simulate other policies against the same
generative environment.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta

import numpy as np
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from sim.latent import (
    BankLatent,
    CustomerLatent,
    DatedOutage,
    balance_available,
    build_bank_latents,
    build_dated_outages,
    outage_multiplier_for_day,
    sample_customer_latents,
)
from sim.params import Params
from sim.schema import (
    Attempt,
    Base,
    Cycle,
    Mandate,
    Merchant,
    Notification,
    Revocation,
)

MERCHANT_CATEGORIES = ["ott", "sip", "insurance", "utility", "saas", "fitness"]


@dataclass
class OutcomeDraw:
    outcome: str  # ATTEMPT_OUTCOMES
    error_source: str | None
    error_step: str | None
    error_reason: str | None


@dataclass
class SimSummary:
    n_mandates: int
    n_attempts: int
    n_successes: int
    n_soft_declines: int
    n_hard_declines: int
    n_rejected_no_pdn: int
    n_revocations: int
    n_cycles_with_failure_then_recovery: int
    n_cycles_with_failure: int

    @property
    def failure_rate(self) -> float:
        failed = self.n_attempts - self.n_successes
        return failed / self.n_attempts if self.n_attempts else 0.0

    @property
    def recovery_rate(self) -> float:
        return (
            self.n_cycles_with_failure_then_recovery / self.n_cycles_with_failure
            if self.n_cycles_with_failure
            else 0.0
        )

    @property
    def monthly_revocation_ratio(self) -> float:
        return self.n_revocations / self.n_mandates if self.n_mandates else 0.0


def attempt_outcome(
    bank: BankLatent,
    customer: CustomerLatent,
    at: datetime,
    amount: float,
    has_valid_pdn: bool,
    params: Params,
    dated_outages: list[DatedOutage],
    rng: np.random.Generator,
    bd_multiplier: float = 1.0,
    prior_attempt_failed: bool = False,
) -> OutcomeDraw:
    """Pure-ish outcome draw for a single attempt. `rejected_no_pdn` fires unconditionally
    when `has_valid_pdn` is False — the mechanism that makes retrying without a fresh
    24h notification expensive under Indian rules (docs/04-DATA-MODEL.md).

    `prior_attempt_failed` correlates same-cycle retries with the prior attempt's outcome
    (persistent low balance / bank issue) instead of treating each retry as an independent
    draw — see `retry_policy.within_cycle_repeat_failure_correlation` in params.yaml.
    """
    if not has_valid_pdn:
        return OutcomeDraw("rejected_no_pdn", "customer", "payment_authorization", "no_pdn")

    dow_weight = bank.dow_weights[at.weekday()]
    outage_mult = outage_multiplier_for_day(bank.bank_id, at.date(), dated_outages, rng)

    td = bank.base_td * (2 - dow_weight) * (2 - outage_mult)
    bd = bank.base_bd * (2 - dow_weight) * bd_multiplier
    td = min(td, 0.5)
    bd = min(bd, 0.9)

    has_funds = balance_available(customer, at, amount, rng)
    if not has_funds:
        bd = max(bd, 0.85)  # insufficient funds dominates when latent balance says no

    raw_fail_prob = min(td + bd, 0.98)
    fail_prob = raw_fail_prob
    if prior_attempt_failed:
        corr = params.get("retry_policy.within_cycle_repeat_failure_correlation")
        fail_prob = corr + (1 - corr) * raw_fail_prob

    roll = rng.random()
    if roll < fail_prob:
        td_share = td / raw_fail_prob if raw_fail_prob > 0 else 0.5
        if rng.random() < td_share:
            return OutcomeDraw(
                "soft_decline", "network", "payment_authentication", "gateway_timeout"
            )
        if rng.random() < 0.05:
            return OutcomeDraw(
                "hard_decline", "bank", "payment_authorization", "mandate_not_active"
            )
        return OutcomeDraw("soft_decline", "bank", "payment_authorization", "insufficient_funds")
    return OutcomeDraw("success", None, None, None)


def revocation_hazard(
    params: Params,
    customer: CustomerLatent,
    cumulative_failure_notifications: int,
    notifications_this_cycle: int,
    consecutive_failed_cycles: int,
    mandate_age_cycles: int,
) -> float:
    base = params.get("revocation.base_hazard_per_cycle")
    per_failure = params.get("revocation.hazard_per_failure_notification")
    per_contact = params.get("revocation.hazard_per_contact_density")
    consec_mult = params.get("revocation.hazard_consecutive_failed_cycles_multiplier")
    halflife = params.get("revocation.mandate_age_protection_halflife_cycles")

    hazard = base + per_failure * cumulative_failure_notifications
    hazard += per_contact * max(0, notifications_this_cycle - 1)
    hazard *= consec_mult ** max(0, consecutive_failed_cycles - 1)
    age_protection = 0.5 ** (mandate_age_cycles / halflife)
    hazard *= 1 - 0.3 * (1 - age_protection)  # older mandates modestly stickier
    hazard *= 0.3 + 1.4 * customer.revocation_propensity  # latent trait scales hazard
    return float(min(hazard, 0.9))


@dataclass
class _MandateState:
    consecutive_failed_cycles: int = 0
    cumulative_failure_notifications: int = 0
    last_date_change_cycle: int | None = None


def run_simulation(
    params: Params,
    seed: int,
    db_path: str,
    n_customers: int | None = None,
    n_cycles: int | None = None,
    n_merchants: int | None = None,
) -> SimSummary:
    rng = np.random.default_rng(seed)

    n_customers = n_customers or params.get("population.n_customers")
    n_cycles = n_cycles or params.get("population.n_cycles")
    n_merchants = n_merchants or params.get("population.n_merchants")

    bank_latents = build_bank_latents(params)
    dated_outages = build_dated_outages(params)
    customer_latents = sample_customer_latents(params, n_customers, rng)

    regime_bank = params.get("regime_shift.bank_id")
    regime_from_cycle = params.get("regime_shift.applies_from_cycle_index")
    regime_bd_mult = params.get("regime_shift.shift_multiplier_bd")

    max_attempts = params.get("retry_policy.max_attempts_default_policy")
    pdn_lead_hours = params.get("retry_policy.pdn_lead_hours")
    fresh_pdn_required = params.get("retry_policy.retry_requires_fresh_pdn")
    min_gap_hours = params.get("retry_policy.min_gap_hours_between_attempts")
    fatigue_cap = params.get("notification.fatigue_cap_per_cycle")
    response_rate = params.get("date_change_offer.response_rate")
    converge_n = params.get("date_change_offer.converge_max_changes_per_n_cycles")
    median_amount = params.get("mandate.amount_distribution_inr.median")
    sigma_amount = params.get("mandate.amount_distribution_inr.sigma")
    afa_threshold = params.get("afa.threshold_inr")
    bd_split = params.get("bd_td_failure_split.business_decline_share_of_failures")
    n_banks_target = params.get("population.n_banks")

    del bd_split, n_banks_target  # documented calibration inputs used indirectly via banks{}

    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)

    base_date = datetime(2026, 1, 1)
    cold_start_cutoff = int(n_customers * 0.9)

    with Session(engine) as session:
        merchants = []
        for m in range(n_merchants):
            merchant = Merchant(
                name=f"Merchant-{m:03d}",
                category=MERCHANT_CATEGORIES[m % len(MERCHANT_CATEGORIES)],
                arpu_band=["low", "mid", "high"][m % 3],
                avg_ticket=float(np.exp(rng.normal(np.log(median_amount), sigma_amount))),
            )
            merchants.append(merchant)
        session.add_all(merchants)
        session.flush()

        summary = SimSummary(
            n_mandates=n_customers,
            n_attempts=0,
            n_successes=0,
            n_soft_declines=0,
            n_hard_declines=0,
            n_rejected_no_pdn=0,
            n_revocations=0,
            n_cycles_with_failure_then_recovery=0,
            n_cycles_with_failure=0,
        )

        for c in customer_latents:
            merchant = merchants[int(rng.integers(0, n_merchants))]
            amount = float(np.exp(rng.normal(np.log(median_amount), sigma_amount)))
            cycle_day = int(np.clip(rng.normal(c.income_day + 2, 2), 1, 28))
            is_cold_start = c.customer_id >= cold_start_cutoff

            mandate = Mandate(
                merchant_id=merchant.id,
                customer_id=c.customer_id,
                method="upi_autopay",
                amount=amount,
                cycle_day=cycle_day,
                created_at=base_date,
                status="active",
                afa_threshold_applicable=amount > afa_threshold,
                is_cold_start=is_cold_start,
                regime_shift_bank=(c.bank_id == regime_bank),
            )
            session.add(mandate)
            session.flush()

            bank = bank_latents[c.bank_id]
            state = _MandateState()
            revoked = False

            for cycle_index in range(1, n_cycles + 1):
                if revoked:
                    break

                due_date = base_date.replace(day=1) + timedelta(
                    days=30 * (cycle_index - 1) + (cycle_day - 1)
                )
                cycle = Cycle(
                    mandate_id=mandate.id,
                    cycle_index=cycle_index,
                    due_date=due_date,
                    status="pending",
                )
                session.add(cycle)
                session.flush()

                bd_mult = 1.0
                if mandate.regime_shift_bank and cycle_index >= regime_from_cycle:
                    bd_mult = regime_bd_mult

                notifications_this_cycle = 0
                cycle_succeeded = False
                had_failure_this_cycle = False

                # date-change offer after two consecutive failed cycles, respecting the
                # converge cap
                if (
                    state.consecutive_failed_cycles >= 2
                    and notifications_this_cycle < fatigue_cap
                    and (
                        state.last_date_change_cycle is None
                        or cycle_index - state.last_date_change_cycle >= converge_n
                    )
                ):
                    accepted = rng.random() < response_rate
                    session.add(
                        Notification(
                            mandate_id=mandate.id,
                            cycle_id=cycle.id,
                            kind="date_change_offer",
                            channel="sms",
                            sent_at=due_date - timedelta(hours=pdn_lead_hours),
                            template_id="date_change_offer_v1",
                            contained_defer_option=True,
                            customer_response="accepted" if accepted else "ignored",
                        )
                    )
                    notifications_this_cycle += 1
                    if accepted:
                        state.last_date_change_cycle = cycle_index
                        cycle_day = int(np.clip(c.income_day + 2, 1, 28))

                prior_attempt_failed = False
                for attempt_index in range(1, max_attempts + 1):
                    if notifications_this_cycle >= fatigue_cap and attempt_index > 1:
                        break  # DOBARA-FATIGUE hard cap

                    scheduled_at = due_date + timedelta(hours=min_gap_hours * (attempt_index - 1))
                    has_valid_pdn = True  # default policy always sends a fresh PDN first
                    if fresh_pdn_required or attempt_index == 1:
                        session.add(
                            Notification(
                                mandate_id=mandate.id,
                                cycle_id=cycle.id,
                                kind="pre_debit",
                                channel="sms",
                                sent_at=scheduled_at - timedelta(hours=pdn_lead_hours),
                                template_id="pdn_v1",
                                contained_defer_option=True,
                            )
                        )
                        notifications_this_cycle += 1

                    draw = attempt_outcome(
                        bank,
                        c,
                        scheduled_at,
                        amount,
                        has_valid_pdn,
                        params,
                        dated_outages,
                        rng,
                        bd_mult,
                        prior_attempt_failed,
                    )
                    prior_attempt_failed = draw.outcome in ("soft_decline", "hard_decline")
                    session.add(
                        Attempt(
                            cycle_id=cycle.id,
                            attempt_index=attempt_index,
                            scheduled_at=scheduled_at,
                            executed_at=scheduled_at,
                            outcome=draw.outcome,
                            error_source=draw.error_source,
                            error_step=draw.error_step,
                            error_reason=draw.error_reason,
                            gateway_ref=f"rzp_test_sim_{uuid.uuid4().hex[:14]}",
                            had_valid_pdn=has_valid_pdn,
                        )
                    )
                    summary.n_attempts += 1

                    if draw.outcome == "success":
                        summary.n_successes += 1
                        cycle_succeeded = True
                        session.add(
                            Notification(
                                mandate_id=mandate.id,
                                cycle_id=cycle.id,
                                kind="post_confirm",
                                channel="push",
                                sent_at=scheduled_at,
                                template_id="post_confirm_v1",
                            )
                        )
                        break
                    if draw.outcome == "rejected_no_pdn":
                        summary.n_rejected_no_pdn += 1
                        continue
                    had_failure_this_cycle = True
                    if draw.outcome == "hard_decline":
                        summary.n_hard_declines += 1
                        break
                    summary.n_soft_declines += 1
                    state.cumulative_failure_notifications += 1

                    hazard = revocation_hazard(
                        params,
                        c,
                        state.cumulative_failure_notifications,
                        notifications_this_cycle,
                        state.consecutive_failed_cycles + 1,
                        cycle_index,
                    )
                    if rng.random() < hazard:
                        revoked = True
                        session.add(Revocation(mandate_id=mandate.id, revoked_at=scheduled_at))
                        summary.n_revocations += 1
                        mandate.status = "revoked"
                        break

                cycle.status = (
                    "success" if cycle_succeeded else ("revoked" if revoked else "failed")
                )
                if had_failure_this_cycle:
                    summary.n_cycles_with_failure += 1
                    if cycle_succeeded:
                        summary.n_cycles_with_failure_then_recovery += 1
                    state.consecutive_failed_cycles = (
                        0 if cycle_succeeded else state.consecutive_failed_cycles + 1
                    )
                elif cycle_succeeded:
                    state.consecutive_failed_cycles = 0

                if revoked:
                    break

        session.commit()

    return summary


def default_db_path(seed: int) -> str:
    return f"data/dobara_seed{seed}.sqlite3"
