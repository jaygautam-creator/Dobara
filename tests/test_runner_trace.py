"""`run_arm(..., trace=True)` must be a pure observation: it may record what happened, and
it may not change what happens.

The per-beat trace (`eval/runner.py::AttemptEvent`) exists so the landing page's
side-by-side demonstration can replay one real mandate under two policies from recorded
data rather than a hand-authored story (`scripts/build_home_demo.py`). That is only worth
anything if the traced run is the same run the harness scores -- so these tests pin both
halves: identical aggregates with the trace on and off, and a trace that reconstructs
those aggregates rather than telling a second, prettier story.
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from agent.models import load_model_bundle
from agent.policy import load_policy
from eval.arms import Arm
from eval.runner import MandateResult, run_arm
from eval.world import build_world
from models.ltv import build_life_table
from sim.params import load_params

N_CUSTOMERS = 120
N_MERCHANTS = 8
SEED = 909
TRAIN_DB_PATH = "data/dobara.sqlite3"


@pytest.fixture(scope="module")
def _setup():
    params = load_params()
    policy = load_policy()
    horizon_cycles = int(params.get("ltv.horizon_cycles"))
    model_bundle = load_model_bundle(TRAIN_DB_PATH)
    life_table = build_life_table(TRAIN_DB_PATH, horizon_cycles)
    world = build_world(params, seed=SEED, n_customers=N_CUSTOMERS, n_merchants=N_MERCHANTS)
    return params, policy, model_bundle, life_table, world


def _run(setup, arm: Arm, trace: bool) -> list[MandateResult]:
    params, policy, model_bundle, life_table, world = setup
    kwargs = {}
    if arm is Arm.DOBARA:
        kwargs = {"policy": policy, "model_bundle": model_bundle, "holdout_fraction": 0.0}
    return run_arm(world, arm, params, life_table, trace=trace, **kwargs)


@pytest.mark.parametrize("arm", [Arm.AGGRESSIVE_8X, Arm.DOBARA])
def test_trace_changes_no_scored_field(_setup, arm: Arm) -> None:
    """Every field the evaluation reports must be identical with the trace on and off --
    compared by clearing `events` and asserting the two result lists are equal, so a field
    added to MandateResult later is covered by this test automatically."""
    untraced = _run(_setup, arm, trace=False)
    traced = _run(_setup, arm, trace=True)

    assert [replace(r, events=[]) for r in traced] == untraced
    assert all(not r.events for r in untraced)
    assert any(r.events for r in traced)


@pytest.mark.parametrize("arm", [Arm.AGGRESSIVE_8X, Arm.DOBARA])
def test_trace_reconstructs_the_aggregates(_setup, arm: Arm) -> None:
    """The beats must add up to the totals they accompany: one recorded attempt per
    counted attempt, the final notification count equal to the mandate's total, and a
    revocation flagged on exactly the mandates the aggregate says revoked."""
    for res in _run(_setup, arm, trace=True):
        if res.routed_to_holdout:
            continue
        attempts = [e for e in res.events if e.kind == "attempt"]
        assert len(attempts) == res.n_attempts
        assert [e.outcome for e in attempts].count("success") == res.n_successes
        if res.events:
            assert res.events[-1].notifications_to_date <= res.n_notifications
        assert any(e.revoked for e in res.events) == res.revoked
        if res.revoked:
            revocation = next(e for e in res.events if e.revoked)
            assert revocation.cycle_index == res.revoked_at_cycle
            assert revocation.ltv_lost_inr == pytest.approx(res.ltv_lost_inr)


def test_dobara_records_why_it_stopped(_setup) -> None:
    """The demonstration's whole point is that the restrained lane stops for a stated
    reason. A stop/abstain beat must carry that reason, never an empty label."""
    results = _run(_setup, Arm.DOBARA, trace=True)
    terminal = [e for r in results for e in r.events if e.kind in ("stop", "abstain", "escalate")]
    assert terminal, "no dobara mandate stopped in this population -- the trace can't be checked"
    assert all(e.reason for e in terminal)
