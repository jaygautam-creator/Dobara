"""Sensitivity analysis over declared `sim/params.yaml` assumptions, per
docs/07-EVAL-SPEC.md "## Sensitivity analysis" — most importantly
`revocation.hazard_per_failure_notification`, since it is a declared assumption (not a
measured fact) and the whole thesis now rests on `dobara` beating `razorpay_default`
across its *entire* declared `sensitivity_range`, not at the single calibrated value (see
docs/DECISIONS.md [2026-08-25] "Corrected: the hazard headline number does not confirm
the thesis").

`sweep_hazard_per_failure_notification` overrides that one leaf's `value` in an
in-memory copy of `Params` (never mutates `sim/params.yaml` on disk) and re-runs
`dobara` and `razorpay_default` at each point using `eval.rng.event_rng`'s common-random-
numbers property: the attempt-outcome draws are identical at every sweep point (the
hazard parameter never enters `attempt_outcome`), so the curve reflects the swept
parameter's effect on revocation, not re-randomized seed noise.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

import numpy as np
from joblib import Parallel, delayed

from agent.models import ModelBundle
from agent.policy import PolicyConfig
from eval.arms import Arm
from eval.metrics import bootstrap_mean_ci
from eval.runner import MandateResult, run_arm
from eval.world import World
from models.ltv import LifeTable
from sim.params import Params


def _with_override(params: Params, dotted_path: str, value: float) -> Params:
    """Returns a new `Params` with one leaf's `value` overridden — a plain dict-copy
    override, not a re-validated `sim/params.yaml` load, since the override is
    intentionally NOT sourced-or-assumption-checked (it's a sweep point, not a config
    change); `sim/params.py`'s validator already ran once when `params` was first loaded.
    """
    import copy

    raw = copy.deepcopy(params.raw)
    node = raw
    parts = dotted_path.split(".")
    for part in parts[:-1]:
        node = node[part]
    node[parts[-1]]["value"] = value
    return replace(params, raw=raw)


def _net_ltv_per_mandate(results: list[MandateResult]) -> np.ndarray:
    return np.array([r.net_ltv_inr for r in results])


@dataclass(frozen=True)
class SweepPoint:
    hazard_per_failure_notification: float
    dobara_mean_net_ltv: float
    dobara_ci: tuple[float, float]
    razorpay_default_mean_net_ltv: float
    razorpay_default_ci: tuple[float, float]
    dobara_minus_razorpay_default: float
    dobara_wins: bool


def _run_one_point(
    value: float,
    world: World,
    params: Params,
    policy: PolicyConfig,
    model_bundle: ModelBundle,
    life_table: LifeTable,
) -> SweepPoint:
    swept_params = _with_override(params, "revocation.hazard_per_failure_notification", value)
    dobara_results = run_arm(
        world,
        Arm.DOBARA,
        swept_params,
        life_table,
        policy=policy,
        model_bundle=model_bundle,
        holdout_fraction=0.0,
    )
    rp_results = run_arm(world, Arm.RAZORPAY_DEFAULT, swept_params, life_table)

    d_point, d_lo, d_hi = bootstrap_mean_ci(_net_ltv_per_mandate(dobara_results))
    r_point, r_lo, r_hi = bootstrap_mean_ci(_net_ltv_per_mandate(rp_results))
    return SweepPoint(
        hazard_per_failure_notification=float(value),
        dobara_mean_net_ltv=d_point,
        dobara_ci=(d_lo, d_hi),
        razorpay_default_mean_net_ltv=r_point,
        razorpay_default_ci=(r_lo, r_hi),
        dobara_minus_razorpay_default=d_point - r_point,
        dobara_wins=d_point > r_point,
    )


def sweep_hazard_per_failure_notification(
    world: World,
    params: Params,
    policy: PolicyConfig,
    model_bundle: ModelBundle,
    life_table: LifeTable,
    points: list[float] | None = None,
    n_jobs: int = 1,
) -> list[SweepPoint]:
    """Each sweep point only depends on the shared `world`/`model_bundle`/`life_table`
    (read-only) plus its own swept `value` — independent across points, so `n_jobs > 1`
    parallelizes across points via `joblib` (each candidate-scoring call inside `dobara`'s
    `decide()` is itself the dominant per-point cost; points don't share that work).
    """
    lo, hi = params.raw["revocation"]["hazard_per_failure_notification"]["sensitivity_range"]
    if points is None:
        points = list(np.linspace(lo, hi, 5))

    if n_jobs == 1:
        return [_run_one_point(v, world, params, policy, model_bundle, life_table) for v in points]

    results = Parallel(n_jobs=n_jobs)(
        delayed(_run_one_point)(v, world, params, policy, model_bundle, life_table) for v in points
    )
    return list(results)
