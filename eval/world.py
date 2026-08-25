"""`World` — the population every arm evaluates against, identical for a given seed.

Extracts the population-shell generation `sim/engine.py::run_simulation` currently does
inline (bank latents, dated outages, customer latents, per-mandate merchant category /
amount / cycle day) into a reusable function, per that module's own docstring: *"`agent/`
(Phase 3) and `eval/` (Phase 4) reuse the pure outcome primitives below ... to simulate
other policies against the same generative environment."* `sim.run` keeps generating
Phase 1/2's training data unchanged; this is the eval-only, DB-free equivalent of its
population step, used to build fresh **held-out** populations (different seeds from the
seed=42 training run) that every arm is scored against identically.

Population-level draws use one sequential `np.random.default_rng(seed)` stream — this
part is *supposed* to be identical and order-independent across arms (every arm gets the
same customers, banks, amounts, cycle days for a given seed). Attempt-level draws (whether
a given attempt succeeds, whether a revocation fires) do NOT use this stream — they use
`eval.rng.event_rng` instead, precisely because those diverge in count/timing across arms
and need per-event determinism instead of shared-stream determinism. See `eval/rng.py`'s
docstring.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from sim.latent import (
    BankLatent,
    CustomerLatent,
    DatedOutage,
    build_bank_latents,
    build_dated_outages,
    sample_customer_latents,
)
from sim.params import Params

MERCHANT_CATEGORIES = ["ott", "sip", "insurance", "utility", "saas", "fitness"]


@dataclass(frozen=True)
class MandateSpec:
    """A mandate's fixed attributes for the eval horizon — everything about it that does
    not depend on which arm is being run."""

    mandate_id: int  # == customer_id: one mandate per simulated customer, as in sim.engine
    customer: CustomerLatent
    merchant_category: str
    amount: float
    cycle_day: int
    is_cold_start: bool
    regime_shift_bank: bool


@dataclass(frozen=True)
class World:
    """Everything every arm sees identically for a given seed. No attempt, notification,
    or revocation history lives here — that is arm-specific and produced by
    `eval/runner.py` starting from this shared population. Building this once per seed
    and handing the same object to every arm is what makes "identical seeds, identical
    simulator state" (docs/07-EVAL-SPEC.md) true rather than aspirational.
    """

    seed: int
    banks: dict[str, BankLatent]
    dated_outages: list[DatedOutage]
    mandates: list[MandateSpec]


def build_world(
    params: Params,
    seed: int,
    n_customers: int | None = None,
    n_merchants: int | None = None,
) -> World:
    rng = np.random.default_rng(seed)
    n_customers = n_customers or int(params.get("population.n_customers"))
    n_merchants = n_merchants or int(params.get("population.n_merchants"))

    banks = build_bank_latents(params)
    dated_outages = build_dated_outages(params)
    customers = sample_customer_latents(params, n_customers, rng)

    median_amount = params.get("mandate.amount_distribution_inr.median")
    sigma_amount = params.get("mandate.amount_distribution_inr.sigma")
    regime_bank = params.get("regime_shift.bank_id")
    cold_start_cutoff = int(n_customers * 0.9)

    mandates = []
    for c in customers:
        merchant_category = MERCHANT_CATEGORIES[
            int(rng.integers(0, n_merchants)) % len(MERCHANT_CATEGORIES)
        ]
        amount = float(np.exp(rng.normal(np.log(median_amount), sigma_amount)))
        cycle_day = int(np.clip(rng.normal(c.income_day + 2, 2), 1, 28))
        mandates.append(
            MandateSpec(
                mandate_id=c.customer_id,
                customer=c,
                merchant_category=merchant_category,
                amount=amount,
                cycle_day=cycle_day,
                is_cold_start=c.customer_id >= cold_start_cutoff,
                regime_shift_bank=(c.bank_id == regime_bank),
            )
        )
    return World(seed=seed, banks=banks, dated_outages=dated_outages, mandates=mandates)
