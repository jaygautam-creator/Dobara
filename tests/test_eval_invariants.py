"""Four hard invariants on the eval harness's arm construction, added 2026-08-25 after a
broken `do_nothing` arm (silently making the originally-scheduled debit every cycle
instead of zero attempts) invalidated an entire full 30-seed run's headline numbers.
These run at a small population so they stay fast enough to gate every change to
`eval/arms.py`/`eval/runner.py`, not just the expensive full harness -- catching this
class of bug here, in seconds, is the whole point; see docs/DECISIONS.md [2026-08-25].
"""

from __future__ import annotations

import numpy as np
import pytest

from agent.models import load_model_bundle
from agent.policy import load_policy
from eval.arms import Arm
from eval.metrics import bootstrap_mean_ci
from eval.runner import run_arm
from eval.world import build_world
from models.ltv import build_life_table
from sim.params import load_params

N_CUSTOMERS = 250
N_MERCHANTS = 10
SEED = 777
TRAIN_DB_PATH = "data/dobara.sqlite3"


@pytest.fixture(scope="module")
def _harness():
    params = load_params()
    policy = load_policy()
    horizon_cycles = int(params.get("ltv.horizon_cycles"))
    model_bundle = load_model_bundle(TRAIN_DB_PATH)
    life_table = build_life_table(TRAIN_DB_PATH, horizon_cycles)
    world = build_world(params, seed=SEED, n_customers=N_CUSTOMERS, n_merchants=N_MERCHANTS)

    results = {
        Arm.DO_NOTHING: run_arm(world, Arm.DO_NOTHING, params, life_table),
        Arm.RAZORPAY_DEFAULT: run_arm(world, Arm.RAZORPAY_DEFAULT, params, life_table),
        Arm.AGGRESSIVE_8X: run_arm(world, Arm.AGGRESSIVE_8X, params, life_table),
        Arm.ORACLE: run_arm(world, Arm.ORACLE, params, life_table),
        Arm.DOBARA: run_arm(
            world,
            Arm.DOBARA,
            params,
            life_table,
            policy=policy,
            model_bundle=model_bundle,
            holdout_fraction=0.0,
        ),
    }
    return results


def test_invariant_1_do_nothing_makes_zero_attempts(_harness):
    """`do_nothing` is the floor: no recovery attempted at all, per docs/07-EVAL-SPEC.md's
    arm table. Revocation only ever fires inside `_draw_attempt` on a failed attempt
    (`sim.engine.revocation_hazard` has no attempt-independent "ambient churn" channel in
    this codebase), so zero attempts structurally implies zero revocations too -- not a
    separate assumption, a direct consequence of the current simulator mechanics.
    """
    results = _harness[Arm.DO_NOTHING]
    assert sum(r.n_attempts for r in results) == 0
    assert sum(r.n_notifications for r in results) == 0
    assert sum(r.gross_recovered_inr for r in results) == 0.0
    assert sum(r.revoked for r in results) == 0
    assert sum(r.net_ltv_inr for r in results) == 0.0


def test_invariant_2_aggressive_8x_attempts_materially_greater_than_razorpay_default(_harness):
    """The lifetime-total `attempts_mean` metric cannot show this (~90% of cycles never
    fail at all regardless of cadence, and revocation-driven early truncation of a
    mandate's remaining cycles further dilutes it) -- the metric that actually reflects a
    cadence's retry ceiling is mean attempts used in cycles whose first attempt failed.
    `razorpay_default` is structurally capped at 3 attempts/cycle here (its own
    `retry_policy.max_attempts_default_policy=4` is cut short by
    `notification.fatigue_cap_per_cycle=3`, which it respects and `aggressive_8x`
    deliberately does not -- bug-for-bug faithful to Phase 1's `sim.engine.run_simulation`,
    not a new eval-harness bug). Empirically (n=800, seed=999, during this fix's
    investigation): razorpay_default ~2.31, aggressive_8x ~2.77 attempts per failed
    cycle (~20% higher) -- asserting >=10% leaves real margin for seed variance while
    still being a materially different number, not an arbitrary epsilon.
    """

    def _mean_attempts_in_failed_cycles(results):
        n_failed = sum(r.n_cycles_with_failure for r in results)
        attempts = sum(r.attempts_in_failed_cycles for r in results)
        assert n_failed > 0, "no failed cycles observed -- population too small to test this"
        return attempts / n_failed

    rp_mean = _mean_attempts_in_failed_cycles(_harness[Arm.RAZORPAY_DEFAULT])
    ag_mean = _mean_attempts_in_failed_cycles(_harness[Arm.AGGRESSIVE_8X])
    assert ag_mean > rp_mean * 1.10, (
        f"aggressive_8x's mean attempts-in-failed-cycles ({ag_mean:.2f}) is not "
        f"materially greater than razorpay_default's ({rp_mean:.2f}) -- aggressive_8x's "
        "distinguishing behaviour (up to 8 retries vs. 3) isn't showing up."
    )


def test_invariant_3_dobara_beats_or_matches_do_nothing(_harness):
    """`STOP`/`ABSTAIN` (which now also stops, see docs/DECISIONS.md [2026-08-25] "Abstain
    must stop, not fall back to an attempt") are always in dobara's candidate space with a
    positivity floor on `E[net]` -- its worst case degenerates to `do_nothing`'s zero-
    attempt behaviour. Losing to `do_nothing` significantly is therefore a logical
    impossibility and always a bug signal, never a legitimate finding.
    """
    dobara_ltv = np.array([r.net_ltv_inr for r in _harness[Arm.DOBARA]])
    do_nothing_ltv = np.array([r.net_ltv_inr for r in _harness[Arm.DO_NOTHING]])
    diff = dobara_ltv - do_nothing_ltv
    point, lo, hi = bootstrap_mean_ci(diff)
    assert hi >= 0, (
        f"dobara's net LTV is significantly BELOW do_nothing's (mean diff {point:.2f}, "
        f"95% CI [{lo:.2f}, {hi:.2f}]) -- logically impossible given STOP/ABSTAIN's "
        "positivity floor; this is a bug, not a finding."
    )


def test_invariant_4_oracle_dominates_and_is_more_efficient(_harness):
    """`oracle` has strictly more information than every other arm (true generative
    probabilities instead of estimates) and a true-value stopping rule -- it must weakly
    dominate every arm on net LTV, and its retry-selectivity should make it use fewer
    attempts than `aggressive_8x`'s blunt up-to-8 cadence.
    """
    net_ltv_by_arm = {arm: sum(r.net_ltv_inr for r in results) for arm, results in _harness.items()}
    oracle_ltv = net_ltv_by_arm[Arm.ORACLE]
    for arm, ltv in net_ltv_by_arm.items():
        if arm is Arm.ORACLE:
            continue
        assert oracle_ltv >= ltv, (
            f"oracle ({oracle_ltv:.2f}) does not dominate {arm.value} ({ltv:.2f})"
        )

    oracle_attempts = sum(r.n_attempts for r in _harness[Arm.ORACLE])
    aggressive_attempts = sum(r.n_attempts for r in _harness[Arm.AGGRESSIVE_8X])
    assert oracle_attempts < aggressive_attempts
