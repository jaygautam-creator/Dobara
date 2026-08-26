"""Sensitivity analysis over declared `sim/params.yaml` assumptions, per
docs/07-EVAL-SPEC.md "## Sensitivity analysis" — most importantly
`revocation.hazard_per_failure_notification`, since it is a declared assumption (not a
measured fact) and the whole thesis now rests on `dobara` beating `razorpay_default`
across its *entire* declared `sensitivity_range`, not at the single calibrated value (see
docs/DECISIONS.md [2026-08-25] "Corrected: the hazard headline number does not confirm
the thesis").

`sweep_hazard_per_failure_notification` overrides that one leaf's `value` in an
in-memory copy of `Params` (never mutates `sim/params.yaml` on disk) and re-runs
`dobara`, `razorpay_default`, and `aggressive_8x` at each point using
`eval.rng.event_rng`'s common-random-numbers property: the attempt-outcome draws are
identical at every sweep point (the hazard parameter never enters `attempt_outcome`), so
the curve reflects the swept parameter's effect on revocation, not re-randomized seed
noise.

**Break-even reporting** (docs/07-EVAL-SPEC.md "## Sensitivity analysis"): the value of
`hazard_per_failure_notification` at which `aggressive_8x` would beat `dobara` on net
LTV — `break_even_vs_aggressive_8x` finds it by linear interpolation between the two
adjacent swept points where `dobara_minus_aggressive_8x` changes sign. If it never
changes sign across the declared range, that is reported honestly (`dobara` beats
`aggressive_8x` at every tested point, or the reverse) rather than extrapolated past data
that was never run.
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
    aggressive_8x_mean_net_ltv: float
    aggressive_8x_ci: tuple[float, float]
    dobara_minus_razorpay_default: float
    dobara_wins: bool
    dobara_minus_aggressive_8x: float
    dobara_beats_aggressive_8x: bool


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
    agg_results = run_arm(world, Arm.AGGRESSIVE_8X, swept_params, life_table)

    d_point, d_lo, d_hi = bootstrap_mean_ci(_net_ltv_per_mandate(dobara_results))
    r_point, r_lo, r_hi = bootstrap_mean_ci(_net_ltv_per_mandate(rp_results))
    a_point, a_lo, a_hi = bootstrap_mean_ci(_net_ltv_per_mandate(agg_results))
    return SweepPoint(
        hazard_per_failure_notification=float(value),
        dobara_mean_net_ltv=d_point,
        dobara_ci=(d_lo, d_hi),
        razorpay_default_mean_net_ltv=r_point,
        razorpay_default_ci=(r_lo, r_hi),
        aggressive_8x_mean_net_ltv=a_point,
        aggressive_8x_ci=(a_lo, a_hi),
        dobara_minus_razorpay_default=d_point - r_point,
        dobara_wins=d_point > r_point,
        dobara_minus_aggressive_8x=d_point - a_point,
        dobara_beats_aggressive_8x=d_point > a_point,
    )


def _break_even(
    points: list[SweepPoint], diff_attr: str, wins_attr: str, other_arm: str
) -> dict[str, object]:
    """Linear interpolation between the two adjacent swept points where the named diff
    attribute changes sign — the `hazard_per_failure_notification` value at which
    `other_arm` would just start beating `dobara`. Per docs/07-EVAL-SPEC.md's "Break-even
    reporting": state the condition under which the conclusion flips, don't extrapolate
    past what was actually run.
    """
    ordered = sorted(points, key=lambda p: p.hazard_per_failure_notification)
    for a, b in zip(ordered, ordered[1:], strict=False):
        y0, y1 = getattr(a, diff_attr), getattr(b, diff_attr)
        if (y0 > 0) != (y1 > 0):
            x0, x1 = a.hazard_per_failure_notification, b.hazard_per_failure_notification
            crossing = x0 + (0.0 - y0) * (x1 - x0) / (y1 - y0)
            return {
                "found": True,
                "hazard_per_failure_notification": crossing,
                "between_points": [x0, x1],
                "note": (
                    f"linear interpolation between the two nearest swept points "
                    f"({x0:.4f}, {x1:.4f}); not itself a re-run value"
                ),
            }
    all_dobara_wins = all(getattr(p, wins_attr) for p in ordered)
    lo, hi = ordered[0].hazard_per_failure_notification, ordered[-1].hazard_per_failure_notification
    return {
        "found": False,
        f"dobara_beats_{other_arm}_at_every_tested_point": all_dobara_wins,
        "note": (
            f"dobara beats {other_arm} at every tested point in [{lo}, {hi}]"
            if all_dobara_wins
            else f"{other_arm} beats dobara at every tested point in [{lo}, {hi}]"
        ),
    }


def break_even_vs_aggressive_8x(points: list[SweepPoint]) -> dict[str, object]:
    """The `hazard_per_failure_notification` value at which `aggressive_8x` would just
    start beating `dobara` on net LTV — docs/07-EVAL-SPEC.md's own break-even ask.
    """
    return _break_even(
        points, "dobara_minus_aggressive_8x", "dobara_beats_aggressive_8x", "aggressive_8x"
    )


def break_even_vs_razorpay_default(points: list[SweepPoint]) -> dict[str, object]:
    """The `hazard_per_failure_notification` value at which `razorpay_default` would beat
    `dobara` on net LTV — not asked for by name in docs/07-EVAL-SPEC.md (which names
    `aggressive_8x`), but the more load-bearing question: it is `dobara`'s own headline
    claim, not `aggressive_8x`'s collapse, that this number can undo. Added 2026-08-26
    after the sweep showed exactly this: `dobara` loses to `razorpay_default` at the
    bottom of the declared range (0.05) despite beating it at the calibrated value
    (0.098) — see docs/DECISIONS.md.
    """
    return _break_even(points, "dobara_minus_razorpay_default", "dobara_wins", "razorpay_default")


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


# Held out from both the seed=42 training population and the eval harness's seeds
# 101-130 -- a fresh, single world (matches this module's own common-random-numbers
# design: one world, swept parameter, not seed variance -- that's the main harness's job).
SENSITIVITY_SEED = 301


def main() -> None:
    import json
    from pathlib import Path

    from agent.models import load_model_bundle
    from agent.policy import load_policy
    from eval.world import build_world
    from models.ltv import build_life_table
    from sim.params import load_params

    params = load_params()
    policy = load_policy()
    n_customers = int(params.get("population.n_customers"))
    horizon_cycles = int(params.get("ltv.horizon_cycles"))
    model_bundle = load_model_bundle("data/dobara.sqlite3")
    life_table = build_life_table("data/dobara.sqlite3", horizon_cycles)
    world = build_world(params, seed=SENSITIVITY_SEED, n_customers=n_customers)

    points = sweep_hazard_per_failure_notification(
        world, params, policy, model_bundle, life_table, n_jobs=5
    )
    break_even_agg = break_even_vs_aggressive_8x(points)
    break_even_rp = break_even_vs_razorpay_default(points)

    out = {
        "seed": SENSITIVITY_SEED,
        "n_customers": n_customers,
        "swept_parameter": "revocation.hazard_per_failure_notification",
        "sensitivity_range": params.raw["revocation"]["hazard_per_failure_notification"][
            "sensitivity_range"
        ],
        "calibrated_value": params.get("revocation.hazard_per_failure_notification"),
        "points": [
            {
                "hazard_per_failure_notification": p.hazard_per_failure_notification,
                "dobara_mean_net_ltv": p.dobara_mean_net_ltv,
                "dobara_ci": list(p.dobara_ci),
                "razorpay_default_mean_net_ltv": p.razorpay_default_mean_net_ltv,
                "razorpay_default_ci": list(p.razorpay_default_ci),
                "aggressive_8x_mean_net_ltv": p.aggressive_8x_mean_net_ltv,
                "aggressive_8x_ci": list(p.aggressive_8x_ci),
                "dobara_minus_razorpay_default": p.dobara_minus_razorpay_default,
                "dobara_wins_vs_razorpay_default": p.dobara_wins,
                "dobara_minus_aggressive_8x": p.dobara_minus_aggressive_8x,
                "dobara_beats_aggressive_8x": p.dobara_beats_aggressive_8x,
            }
            for p in points
        ],
        "break_even_vs_aggressive_8x": break_even_agg,
        "break_even_vs_razorpay_default": break_even_rp,
    }
    Path("artifacts").mkdir(exist_ok=True)
    Path("artifacts/sensitivity.json").write_text(json.dumps(out, indent=2))
    print(f"wrote artifacts/sensitivity.json ({len(points)} points)")
    print()
    for p in sorted(points, key=lambda p: p.hazard_per_failure_notification):
        print(
            f"hazard={p.hazard_per_failure_notification:.4f}  "
            f"dobara={p.dobara_mean_net_ltv:>9,.2f}  "
            f"razorpay_default={p.razorpay_default_mean_net_ltv:>9,.2f}  "
            f"aggressive_8x={p.aggressive_8x_mean_net_ltv:>9,.2f}  "
            f"dobara_vs_rp={'WIN' if p.dobara_wins else 'lose':4s}  "
            f"dobara_vs_agg={'WIN' if p.dobara_beats_aggressive_8x else 'lose'}"
        )
    print()
    print("break_even_vs_aggressive_8x:", json.dumps(break_even_agg, indent=2))
    print("break_even_vs_razorpay_default:", json.dumps(break_even_rp, indent=2))


if __name__ == "__main__":
    main()
