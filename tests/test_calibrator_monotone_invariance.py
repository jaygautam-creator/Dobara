"""Regression test for the bug class found in `docs/DECISIONS.md` [2026-09-01]
"Part A: three tie-rate numbers that should have been equal, weren't".

The property that SHOULD hold, and that the investigation's own diagnostic confirmed
does hold: for a fixed decision (fixed `DecisionContext`, fixed legal candidate set),
recalibrating `ScheduleDebit`'s `p_success` with any strictly monotone function cannot
change which `ScheduleDebit` candidates tie for the best `expected_net` *among
ScheduleDebit candidates* — `expected_net = p_success*(amount + hazard_raw*ltv) -
hazard_raw*ltv - cost` is a strictly increasing affine function of `p_success` alone
(all other terms fixed within one decision, per `agent/decide.py::_net_score`), so a
strictly monotone recalibration of `p_success` is itself a strictly monotone
recalibration of `expected_net`, which preserves exact ties by definition.

**What this test does NOT assert**, because it is false, and asserting it caused the
original confusion: that the ANY-CANDIDATE argmax tie rate (across ScheduleDebit AND
`Stop`/`EscalateToHuman`/`OfferDateChange`, whose `expected_net` per
`agent/decide.py::_score_all` is a FIXED constant — 0.0 or 0.01 — independent of the
recovery calibrator entirely) is invariant under recalibration. It is not: a
recalibrated `ScheduleDebit` score can coincidentally land exactly on that fixed
constant under one calibrator and not another, purely as a function of the
calibrator's absolute output scale. That is real, measured behavior
(`scripts/held_out_calibrator_verification.py`'s tie counts, which are the pre-registered
metric), not a bug — see the DECISIONS.md entry for the empirical breakdown.
"""

from __future__ import annotations

import dataclasses
from typing import Any

import numpy as np

from agent.actions import ScheduleDebit
from agent.compliance import is_hard_compliant
from agent.decide import _generate_candidates, _score_all
from agent.models import load_model_bundle
from agent.policy import load_policy
from eval.world import build_world
from sim.params import load_params

DB_PATH = "data/dobara.sqlite3"
ARTIFACTS_DIR = "artifacts"
N_MANDATES = 40
SEED = 9001


class _IdentityWrap:
    def predict(self, x: np.ndarray) -> np.ndarray:
        return np.asarray(np.clip(np.asarray(x, dtype=float), 0.0, 1.0))


class _SyntheticMonotoneWrap:
    """An arbitrary strictly INCREASING function of the raw score, unrelated to any
    fitted calibrator -- picked to be nothing like isotonic's step function or Platt's
    sigmoid, so this test cannot be accidentally passing only because of a coincidental
    property of those two specific fits. Only increasing, deliberately: a probability
    calibrator that inverted the raw score's ranking would map "more likely to succeed"
    to "less likely" and would never be fit in practice (confirmed here too -- the real
    Platt/beta fits both have positive coefficients on the raw score). A DECREASING
    monotone map is a real counterexample to "the tied set is preserved" as stated --
    it preserves the tied set at the ARGMIN, not the argmax -- so it is intentionally
    not exercised by this test; the property under test is specifically about
    argmax-preserving (i.e. increasing) recalibration, which is what every calibrator
    this repo has ever fit actually is."""

    def predict(self, x: np.ndarray) -> np.ndarray:
        x = np.asarray(x, dtype=float)
        # tanh of a scaled, shifted raw score -- strictly increasing, bounded, smooth,
        # with no relationship to the production isotonic calibrator's knots.
        return np.asarray(0.5 + 0.5 * np.tanh(4.0 * x - 2.0))


class _SyntheticMonotoneWrapSteep(_SyntheticMonotoneWrap):
    """A second, differently-shaped strictly increasing function (steeper, shifted) --
    exercises the invariant against more than one arbitrary increasing map."""

    def predict(self, x: np.ndarray) -> np.ndarray:
        x = np.asarray(x, dtype=float)
        return np.asarray(0.5 + 0.5 * np.tanh(12.0 * x - 7.0))


def _tied_schedule_debit_sets(legal: list[Any], nets: list[float]) -> frozenset[int]:
    sd_idx = [i for i, a in enumerate(legal) if isinstance(a, ScheduleDebit)]
    if len(sd_idx) < 2:
        return frozenset()
    sd_nets = [nets[i] for i in sd_idx]
    best = max(sd_nets)
    return frozenset(i for i in sd_idx if nets[i] == best)


def test_schedule_debit_only_tie_set_is_invariant_under_monotone_recalibration() -> None:
    """The property Part A's investigation actually confirmed: swap in the raw
    (identity) calibrator vs. two differently-shaped synthetic strictly INCREASING
    calibrators and assert the SCHEDULEDEBIT-ONLY tied-candidate set is
    identical for every decision with 2+ ScheduleDebit candidates. This is the
    invariant the "must be identical" intuition in Part A was actually reaching for --
    scoped correctly, it is true and this test locks it in."""
    params = load_params()
    policy = load_policy()
    bundle = load_model_bundle(DB_PATH, ARTIFACTS_DIR)
    world = build_world(params, seed=SEED, n_customers=N_MANDATES)

    calibrators = {
        "identity": _IdentityWrap(),
        "monotone_increasing_a": _SyntheticMonotoneWrap(),
        "monotone_increasing_b": _SyntheticMonotoneWrapSteep(),
    }
    bundles = {
        name: dataclasses.replace(
            bundle, recovery=dataclasses.replace(bundle.recovery, lgbm_calibrator=cal)
        )
        for name, cal in calibrators.items()
    }

    n_checked = 0
    for m in world.mandates:
        from datetime import datetime, timedelta

        due_date = datetime(2026, 1, 1) + timedelta(days=(m.cycle_day - 1))
        from agent.context import DecisionContext

        ctx = DecisionContext(
            mandate_id=m.mandate_id,
            cycle_id=1,
            cycle_index=1,
            merchant_category=m.merchant_category,
            bank_id=m.customer.bank_id,
            method="upi_autopay",
            amount=m.amount,
            afa_threshold_applicable=m.amount > float(params.get("afa.threshold_inr")),
            now=due_date,
            cycle_due_date=due_date,
            cycle_end=due_date + timedelta(days=30),
            attempt_index=1,
            last_attempt_at=None,
            last_attempt_outcome=None,
            n_attempts_to_date=0,
            n_successes_to_date=0,
            prior_failures_this_cycle=0,
            consecutive_failed_cycles=0,
            prev_error_source=None,
            prev_error_step=None,
            prev_error_reason=None,
            failure_notifications_this_cycle=0,
            total_contacts_30d=0,
            days_since_first_failure_this_cycle=0,
            has_customer_engaged_with_notice=False,
            notifications_sent_this_cycle=0,
            notification_cost_spent_this_cycle_inr=0.0,
            last_pdn_sent_at=None,
            has_declared_preferred_day=False,
            declared_preferred_day=None,
            date_change_last_offered_cycle_index=None,
            customer_opted_out=False,
            mandate_revoked=False,
        )
        candidates = _generate_candidates(ctx, policy)
        legal = [a for a in candidates if is_hard_compliant(a, ctx, policy)]
        n_sd = sum(1 for a in legal if isinstance(a, ScheduleDebit))
        if n_sd < 2:
            continue
        n_checked += 1

        tied_sets = {}
        for name, b in bundles.items():
            scores = _score_all(legal, ctx, b)
            nets = [round(s.expected_net, 6) for s in scores]
            tied_sets[name] = _tied_schedule_debit_sets(legal, nets)

        reference = tied_sets["identity"]
        for name, tied in tied_sets.items():
            assert tied == reference, (
                f"mandate {m.mandate_id}: ScheduleDebit-only tied set under {name!r} "
                f"({sorted(tied)}) differs from identity ({sorted(reference)}) -- "
                "monotone recalibration must preserve exact ties within a single "
                "candidate type whose expected_net is an affine function of p_success alone"
            )

    assert n_checked >= 10, (
        f"only {n_checked} decisions had 2+ ScheduleDebit candidates -- test population "
        "too small to exercise the invariant meaningfully; increase N_MANDATES"
    )
