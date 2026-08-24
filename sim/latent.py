"""Latent (hidden) state: the customer balance-availability process and per-bank failure
generators. **This module must never be imported by `features/`** — a test enforces it
(`tests/test_latent_isolation.py`). Exposing this to features would let the agent learn its
own generator and make the evaluation circular; it is the single most important design
property of the whole project. See docs/04-DATA-MODEL.md.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

import numpy as np

from sim.params import Params

BANK_IDS: list[str] = ["SBI", "HDFC", "ICICI", "AXIS", "KOTAK", "PNB", "BOB", "YES"]


@dataclass(frozen=True)
class CustomerLatent:
    customer_id: int
    bank_id: str
    income_day: int  # day of month, 1-28
    income_amount: float
    spend_decay_per_day: float
    revocation_propensity: float  # 0-1 multiplier on hazard, latent trait


@dataclass(frozen=True)
class BankLatent:
    bank_id: str
    base_td: float
    base_bd: float
    dow_weights: list[float]
    minor_outage_rate_per_month: float


@dataclass(frozen=True)
class DatedOutage:
    day: date
    duration_hours: float
    severity_success_multiplier: float


def build_bank_latents(params: Params) -> dict[str, BankLatent]:
    banks: dict[str, BankLatent] = {}
    dow = params.get("dow_profile.weights")
    minor_rate = params.get("outages.background_minor_outage_rate_per_bank_per_month")
    for bank_id in BANK_IDS:
        base_td = params.get(f"banks.{bank_id}.base_td")
        base_bd = params.get(f"banks.{bank_id}.base_bd")
        banks[bank_id] = BankLatent(
            bank_id=bank_id,
            base_td=base_td,
            base_bd=base_bd,
            dow_weights=list(dow),
            minor_outage_rate_per_month=minor_rate,
        )
    return banks


def build_dated_outages(params: Params) -> list[DatedOutage]:
    events = params.raw["outages"]["dated_events"]
    out = []
    for ev in events:
        y, m, d = (int(x) for x in ev["date"].split("-"))
        out.append(
            DatedOutage(
                day=date(y, m, d),
                duration_hours=ev["duration_hours"]["value"],
                severity_success_multiplier=ev["severity_success_multiplier"]["value"],
            )
        )
    return out


def sample_customer_latents(
    params: Params, n_customers: int, rng: np.random.Generator
) -> list[CustomerLatent]:
    salary_share = params.get("balance_process.salary_cluster_share")
    salary_std = params.get("balance_process.salary_day_std_days")
    spend_decay = params.get("balance_process.spend_decay_per_day")
    bank_ids = rng.choice(BANK_IDS, size=n_customers)
    is_salary = rng.random(n_customers) < salary_share
    income_day = np.where(
        is_salary,
        np.clip(rng.normal(1, salary_std, n_customers), 1, 5),
        rng.integers(10, 26, n_customers),
    ).astype(int)
    income_amount = np.exp(rng.normal(np.log(25000), 0.5, n_customers))
    propensity = rng.beta(2, 6, n_customers)  # right-skewed: most customers low propensity
    out = []
    for i in range(n_customers):
        out.append(
            CustomerLatent(
                customer_id=i,
                bank_id=str(bank_ids[i]),
                income_day=int(income_day[i]),
                income_amount=float(income_amount[i]),
                spend_decay_per_day=spend_decay,
                revocation_propensity=float(propensity[i]),
            )
        )
    return out


def balance_available(
    customer: CustomerLatent, at: datetime, amount_needed: float, rng: np.random.Generator
) -> bool:
    """Whether the latent balance process has `amount_needed` available at `at`.

    Days-since-income determines a decaying probability mass; near-zero balance after the
    income month makes the amount unaffordable with rising probability. This is the process
    `features/` is never allowed to see directly.
    """
    days_in_month = 30
    days_since_income = (at.day - customer.income_day) % days_in_month
    remaining_fraction = (1 - customer.spend_decay_per_day) ** days_since_income
    expected_balance = customer.income_amount * remaining_fraction
    # noisy balance draw, floored at 0
    noise = rng.lognormal(mean=0.0, sigma=0.35)
    actual_balance = max(0.0, expected_balance * noise)
    return actual_balance >= amount_needed


def outage_multiplier_for_day(
    bank_id: str, day_: date, dated_outages: list[DatedOutage], rng: np.random.Generator
) -> float:
    for ev in dated_outages:
        if ev.day == day_:
            return ev.severity_success_multiplier
    return 1.0
