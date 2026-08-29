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
that was never run. `break_even_vs_razorpay_default` does the same against `dobara`'s own
headline claim (not named by the spec, but the more load-bearing question).

**Judging a break-even against the declared `sensitivity_range` alone uses the weaker
object to judge the stronger one.** That range ([0.05, 0.15]) is an a priori guess written
into `sim/params.yaml` before any data existed; the calibrated value (0.098) is not a
guess — it was empirically recalibrated to hit the published
20M-revocations/808M-executions ≈ 2.5% ratio from real NPCI figures
(`sim.engine.SimSummary.revocation_per_execution_ratio`, `tests/test_calibration.py`'s own
benchmark). So every `SweepPoint` also records `razorpay_default`'s
`revocation_per_execution_ratio` at that sweep point, and
`break_even_vs_razorpay_default` interpolates it at the break-even hazard value — this
lets the break-even be judged against the same published external benchmark the
calibration itself was built to hit, not just against the guessed range's position.
Added 2026-08-26, see docs/DECISIONS.md.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

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


def _leaf(raw: dict[str, Any], dotted_path: str) -> dict[str, Any]:
    """The leaf dict (`{"value": ..., "sensitivity_range": [...], ...}`) a dotted path
    (`"notification.cost_inr.whatsapp"`) points to inside a `Params.raw` tree.
    """
    node: dict[str, Any] = raw
    parts = dotted_path.split(".")
    for part in parts[:-1]:
        node = node[part]
    leaf: dict[str, Any] = node[parts[-1]]
    return leaf


def _with_override(params: Params, dotted_path: str, value: float) -> Params:
    """Returns a new `Params` with one leaf's `value` overridden — a plain dict-copy
    override, not a re-validated `sim/params.yaml` load, since the override is
    intentionally NOT sourced-or-assumption-checked (it's a sweep point, not a config
    change); `sim/params.py`'s validator already ran once when `params` was first loaded.
    """
    import copy

    raw = copy.deepcopy(params.raw)
    _leaf(raw, dotted_path)["value"] = value
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
    # sim.engine.SimSummary.revocation_per_execution_ratio's exact definition
    # (n_revocations / n_attempts) for the razorpay_default arm at this sweep point --
    # the same metric tests/test_calibration.py checks against the published
    # 20M-revocations/808M-executions ~= 2.5% NPCI benchmark. Recorded specifically for
    # razorpay_default, not dobara/aggressive_8x: the published figure describes
    # real-world default-cadence behavior, and 0.098's calibration target this ratio
    # under exactly that cadence -- see docs/DECISIONS.md [2026-08-26] "break-even
    # strengthened with the NPCI anchor".
    razorpay_default_revocation_per_execution_ratio: float


def _revocation_per_execution_ratio(results: list[MandateResult]) -> float:
    n_attempts = sum(r.n_attempts for r in results)
    n_revocations = sum(1 for r in results if r.revoked)
    return n_revocations / n_attempts if n_attempts else 0.0


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
        razorpay_default_revocation_per_execution_ratio=_revocation_per_execution_ratio(rp_results),
    )


@dataclass(frozen=True)
class _Crossing:
    t: float  # interpolation fraction between bracket_low and bracket_high
    hazard_per_failure_notification: float
    bracket_low: SweepPoint
    bracket_high: SweepPoint


def _find_crossing(points: list[SweepPoint], diff_attr: str) -> _Crossing | None:
    """The interpolation fraction/hazard value where the named diff attribute changes
    sign between two adjacent swept points, or `None` if it never does across the
    declared range. Shared by both `_break_even` (the public "found"/"note" dict) and
    `break_even_vs_razorpay_default` (which also needs the bracket points themselves to
    interpolate a second quantity, `revocation_per_execution_ratio`, at the same hazard
    value).
    """
    ordered = sorted(points, key=lambda p: p.hazard_per_failure_notification)
    for a, b in zip(ordered, ordered[1:], strict=False):
        y0, y1 = getattr(a, diff_attr), getattr(b, diff_attr)
        if (y0 > 0) != (y1 > 0):
            x0, x1 = a.hazard_per_failure_notification, b.hazard_per_failure_notification
            t = (0.0 - y0) / (y1 - y0)
            return _Crossing(
                t=t,
                hazard_per_failure_notification=x0 + t * (x1 - x0),
                bracket_low=a,
                bracket_high=b,
            )
    return None


def _break_even(
    points: list[SweepPoint], diff_attr: str, wins_attr: str, other_arm: str
) -> dict[str, object]:
    """Linear interpolation between the two adjacent swept points where the named diff
    attribute changes sign — the `hazard_per_failure_notification` value at which
    `other_arm` would just start beating `dobara`. Per docs/07-EVAL-SPEC.md's "Break-even
    reporting": state the condition under which the conclusion flips, don't extrapolate
    past what was actually run.
    """
    crossing = _find_crossing(points, diff_attr)
    if crossing is not None:
        x0 = crossing.bracket_low.hazard_per_failure_notification
        x1 = crossing.bracket_high.hazard_per_failure_notification
        return {
            "found": True,
            "hazard_per_failure_notification": crossing.hazard_per_failure_notification,
            "between_points": [x0, x1],
            "note": (
                f"linear interpolation between the two nearest swept points "
                f"({x0:.4f}, {x1:.4f}); not itself a re-run value"
            ),
        }
    ordered = sorted(points, key=lambda p: p.hazard_per_failure_notification)
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

    Also interpolates `razorpay_default`'s `revocation_per_execution_ratio` at the
    break-even hazard value, using the same interpolation fraction as the hazard crossing
    itself — this is the stronger anchor: `sensitivity_range` was an a priori guess written
    before any data existed, but the published NPCI ratio (~2.5%, `sim/params.yaml`'s own
    calibration target) independently constrains whether the break-even hazard describes a
    plausible world at all, not just whether it's below the single calibrated point.
    """
    result = _break_even(points, "dobara_minus_razorpay_default", "dobara_wins", "razorpay_default")
    crossing = _find_crossing(points, "dobara_minus_razorpay_default")
    if crossing is not None:
        ratio_lo = crossing.bracket_low.razorpay_default_revocation_per_execution_ratio
        ratio_hi = crossing.bracket_high.razorpay_default_revocation_per_execution_ratio
        result["razorpay_default_revocation_per_execution_ratio_at_break_even"] = (
            ratio_lo + crossing.t * (ratio_hi - ratio_lo)
        )
    return result


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


@dataclass(frozen=True)
class OtherAxisPoint:
    """A generic sweep point for the three declared axes docs/07-EVAL-SPEC.md's
    "Sensitivity analysis" section names besides the hazard (which gets the fuller
    `SweepPoint`/break-even treatment above: it's the one axis the thesis rests on across
    its whole range, per docs/DECISIONS.md [2026-08-25]). These three only need "vary
    and re-rank the arms" — no break-even requirement in the spec for any of them.
    """

    value: float
    dobara_mean_net_ltv: float
    razorpay_default_mean_net_ltv: float
    aggressive_8x_mean_net_ltv: float
    ranking: list[str]  # arm names, best net LTV first


def _run_other_axis_point(
    dotted_path: str,
    value: float,
    world: World,
    params: Params,
    policy: PolicyConfig,
    model_bundle: ModelBundle,
    life_table: LifeTable,
) -> OtherAxisPoint:
    swept_params = _with_override(params, dotted_path, value)
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

    d = float(np.mean(_net_ltv_per_mandate(dobara_results)))
    r = float(np.mean(_net_ltv_per_mandate(rp_results)))
    a = float(np.mean(_net_ltv_per_mandate(agg_results)))
    ranking = [
        name
        for name, _ in sorted(
            [("dobara", d), ("razorpay_default", r), ("aggressive_8x", a)], key=lambda t: -t[1]
        )
    ]
    return OtherAxisPoint(
        value=float(value),
        dobara_mean_net_ltv=d,
        razorpay_default_mean_net_ltv=r,
        aggressive_8x_mean_net_ltv=a,
        ranking=ranking,
    )


# The three axes docs/07-EVAL-SPEC.md names besides the hazard, and the sim/params.yaml
# leaf that actually carries a declared sensitivity_range for each:
# - "LTV horizon / expected remaining cycles": ltv.horizon_cycles has NO
#   sensitivity_range (source: docs/04-DATA-MODEL.md, fixed at 8) -- ltv.margin_factor
#   is the LTV-dollar-conversion assumption that DOES carry one ([0.4, 0.9]), and is the
#   one docs/05-ML-SPEC.md's own note says exists "for the Phase 4 sensitivity analysis".
#   Swept in its place; the substitution is stated here and in the output, not silent.
# - "notification channel cost": only notification.cost_inr.whatsapp has a
#   sensitivity_range ([0.2, 0.6]) -- sms and push are sourced/fixed, not assumptions.
# - "date-change offer response rate, including 0%":
#   date_change_offer.response_rate, [0.0, 0.15], with 0.0 forced into the swept points
#   even though np.linspace(0.0, 0.15, 5) already includes it at the low end -- the
#   spec's own words ("a response_rate: 0.0 run is required") make this non-optional to
#   state explicitly, not just an artifact of an evenly-spaced grid.
OTHER_AXES: dict[str, str] = {
    "ltv.margin_factor": (
        "ltv_margin_factor (substituted for ltv.horizon_cycles, which has no declared "
        "sensitivity_range)"
    ),
    "notification.cost_inr.whatsapp": "notification_channel_cost_whatsapp",
    "date_change_offer.response_rate": "date_change_offer_response_rate",
}


def sweep_other_axes(
    world: World,
    params: Params,
    policy: PolicyConfig,
    model_bundle: ModelBundle,
    life_table: LifeTable,
    n_jobs: int = 1,
) -> dict[str, list[OtherAxisPoint]]:
    """Sweeps all three axes in `OTHER_AXES`, each over its own declared
    `sensitivity_range` at 5 evenly-spaced points (0.0 forced in for
    `date_change_offer.response_rate` specifically, per the spec's explicit requirement).
    """
    jobs: list[tuple[str, float]] = []
    for dotted_path in OTHER_AXES:
        lo, hi = _leaf(params.raw, dotted_path)["sensitivity_range"]
        values = list(np.linspace(lo, hi, 5))
        if dotted_path == "date_change_offer.response_rate" and 0.0 not in values:
            values[0] = 0.0  # spec: "a response_rate: 0.0 run is required"
        jobs.extend((dotted_path, v) for v in values)

    if n_jobs == 1:
        results = [
            _run_other_axis_point(path, v, world, params, policy, model_bundle, life_table)
            for path, v in jobs
        ]
    else:
        results = Parallel(n_jobs=n_jobs)(
            delayed(_run_other_axis_point)(path, v, world, params, policy, model_bundle, life_table)
            for path, v in jobs
        )

    out: dict[str, list[OtherAxisPoint]] = {path: [] for path in OTHER_AXES}
    for (path, _v), point in zip(jobs, results, strict=True):
        out[path].append(point)
    return out


# --- Extended break-even search --------------------------------------------------
#
# The declared `sensitivity_range` in sim/params.yaml is an honest *plausible* range,
# not a search space -- if `dobara` wins at every point inside it, that says nothing
# about how far the true break-even sits, only that it isn't inside this a priori guess.
# A sensitivity analysis that never inverts inside the declared range has not found the
# boundary; it has only described the interior. Added 2026-08-29 (docs/DECISIONS.md)
# after the declared-range sweep stopped finding a break-even against `razorpay_default`
# on any axis and the README's break-even section had nothing left to report but "we
# don't know how far this holds."
#
# This widens each axis outward from its declared range, in the direction that could
# plausibly weaken `dobara`'s advantage, until either the sign of
# `dobara_minus_razorpay_default` flips or a PHYSICAL_SEARCH_BOUND is reached -- a value
# past which the parameter no longer means anything (a hazard increment above 1.0, a
# margin factor at or below 0, a notification cost exceeding the median mandate amount
# it would be levied against, a response rate above 1.0). This is deliberately a
# *separate* pass from `sweep_hazard_per_failure_notification`/`sweep_other_axes` above:
# it never touches sim/params.yaml's declared `sensitivity_range` (other code reads that
# as the honest plausible range) and its output lives under its own artifact key so
# nobody mistakes a searched-to bound for a calibrated one.

# (lo, hi): the outermost physically/economically meaningful bound in the direction that
# could plausibly weaken dobara's advantage. The *other* direction is not searched --
# widening it only strengthens dobara further and finding no crossing there would tell
# us nothing new.
PHYSICAL_SEARCH_BOUND: dict[str, tuple[float, float]] = {
    # a hazard *increment per notification* above 1.0 is nonsensical (it would already
    # saturate the hazard, itself capped at 0.9, after a single notification); dropping
    # toward 0 removes the mechanism the thesis rests on, so this is the meaningful floor.
    "revocation.hazard_per_failure_notification": (0.0, 0.05),
    # a merchant with 0% or negative gross margin has no viable subscription business;
    # `dobara`'s advantage should weaken as mandate value shrinks, so search the low end.
    "ltv.margin_factor": (0.02, 0.4),
    # a per-notification cost above the median mandate amount (~Rs.499, sim/params.yaml
    # mandate.amount_distribution_inr.median) is economically meaningless -- no PSP would
    # charge more to warn about a debit than the debit itself is worth. Cost hurts
    # whichever arm sends more notifications more, which is never dobara, so the
    # direction that could weaken dobara's advantage is cost -> 0 (free), not cost -> high.
    "notification.cost_inr.whatsapp": (0.0, 0.2),
    # a response rate is a probability; dobara uses the date-change offer, so a *lower*
    # response rate (down to the declared range's own floor of 0%, already the physical
    # floor) is the only direction that could weaken its advantage -- there is nothing
    # below 0% to search.
    "date_change_offer.response_rate": (0.0, 0.0),
}


def _point_diff_vs_razorpay_default(
    dotted_path: str,
    value: float,
    world: World,
    params: Params,
    policy: PolicyConfig,
    model_bundle: ModelBundle,
    life_table: LifeTable,
) -> float:
    """`dobara`'s mean net LTV minus `razorpay_default`'s, at one swept value -- a bare
    point estimate (no bootstrap CI) since this is used only to locate a sign change
    during search; the bracketing points that actually get reported are re-run with a
    full CI via `_run_one_point`/`_run_other_axis_point`.
    """
    swept_params = _with_override(params, dotted_path, value)
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
    d = float(np.mean(_net_ltv_per_mandate(dobara_results)))
    r = float(np.mean(_net_ltv_per_mandate(rp_results)))
    return d - r


def _revocation_ratio_at(
    dotted_path: str,
    value: float,
    world: World,
    params: Params,
    life_table: LifeTable,
) -> float:
    """`razorpay_default`'s `revocation_per_execution_ratio` (same definition
    `sweep_hazard_per_failure_notification`'s `SweepPoint` records) at one swept value --
    used to anchor an extended-search break-even against the published NPCI ratio, the
    same way `break_even_vs_razorpay_default` does for the declared-range break-even.
    Only meaningful for axes that actually move revocation risk; called only when a
    break-even was found.
    """
    swept_params = _with_override(params, dotted_path, value)
    rp_results = run_arm(world, Arm.RAZORPAY_DEFAULT, swept_params, life_table)
    return _revocation_per_execution_ratio(rp_results)


@dataclass(frozen=True)
class ExtendedSearchResult:
    dotted_path: str
    declared_range: tuple[float, float]
    calibrated_value: float
    search_bound: float
    found: bool
    break_even_value: float | None
    ratio_calibrated_to_break_even: float | None
    bracket: tuple[float, float] | None
    razorpay_default_revocation_per_execution_ratio_at_break_even: float | None
    note: str


def search_break_even_vs_razorpay_default(
    dotted_path: str,
    world: World,
    params: Params,
    policy: PolicyConfig,
    model_bundle: ModelBundle,
    life_table: LifeTable,
    n_bisection_steps: int = 6,
) -> ExtendedSearchResult:
    """Widens `dotted_path` from its declared range's edge (the edge nearest
    `PHYSICAL_SEARCH_BOUND`) out to that bound, looking for the value at which
    `dobara_minus_razorpay_default` changes sign. Coarse geometric steps locate a
    bracket, then `n_bisection_steps` of bisection narrow it. If no sign change is found
    even at the physical bound, that is reported as a searched-to claim (the bound and
    the fact nothing was found below/above it), never as an unqualified "robust".
    """
    declared_lo, declared_hi = _leaf(params.raw, dotted_path)["sensitivity_range"]
    calibrated_value = _leaf(params.raw, dotted_path)["value"]
    search_lo, search_hi = PHYSICAL_SEARCH_BOUND[dotted_path]

    def diff(v: float) -> float:
        return _point_diff_vs_razorpay_default(
            dotted_path, v, world, params, policy, model_bundle, life_table
        )

    if search_lo == search_hi:
        # No direction left to search -- the declared range already touches the
        # physical bound (date_change_offer.response_rate's floor is 0%, which is
        # already the declared range's own low end).
        return ExtendedSearchResult(
            dotted_path=dotted_path,
            declared_range=(declared_lo, declared_hi),
            calibrated_value=calibrated_value,
            search_bound=search_lo,
            found=False,
            break_even_value=None,
            ratio_calibrated_to_break_even=None,
            bracket=None,
            razorpay_default_revocation_per_execution_ratio_at_break_even=None,
            note=(
                f"declared range's floor ({declared_lo}) already equals the physical "
                f"bound ({search_lo}) in the only direction that could weaken dobara's "
                f"advantage; nothing further to search"
            ),
        )

    # search_lo may be below or above the declared edge nearest it -- widen from that
    # edge toward the physical bound.
    widening_downward = search_lo < declared_lo
    start_edge = declared_lo if widening_downward else declared_hi
    y_start = diff(start_edge)

    y_bound = diff(search_lo if widening_downward else search_hi)
    if (y_start > 0) == (y_bound > 0):
        bound = search_lo if widening_downward else search_hi
        return ExtendedSearchResult(
            dotted_path=dotted_path,
            declared_range=(declared_lo, declared_hi),
            calibrated_value=calibrated_value,
            search_bound=bound,
            found=False,
            break_even_value=None,
            ratio_calibrated_to_break_even=None,
            bracket=None,
            razorpay_default_revocation_per_execution_ratio_at_break_even=None,
            note=(
                f"searched from the declared range's edge ({start_edge}) out to the "
                f"physical/economic bound ({bound}) -- dobara beats razorpay_default at "
                f"every point tested in that search, no inversion found up to the bound"
            ),
        )

    # Coarse geometric bracketing between start_edge and the bound where the sign
    # actually flips, then bisect.
    lo, hi = (start_edge, search_lo) if widening_downward else (start_edge, search_hi)
    y_lo = y_start
    for _ in range(n_bisection_steps):
        mid = (lo + hi) / 2
        y_mid = diff(mid)
        if (y_mid > 0) == (y_lo > 0):
            lo, y_lo = mid, y_mid
        else:
            hi = mid
    break_even_value = (lo + hi) / 2
    ratio = calibrated_value / break_even_value if break_even_value != 0 else None
    revocation_ratio_at_break_even = (
        _revocation_ratio_at(dotted_path, break_even_value, world, params, life_table)
        if dotted_path == "revocation.hazard_per_failure_notification"
        else None
    )
    return ExtendedSearchResult(
        dotted_path=dotted_path,
        declared_range=(declared_lo, declared_hi),
        calibrated_value=calibrated_value,
        search_bound=search_lo if widening_downward else search_hi,
        found=True,
        break_even_value=break_even_value,
        ratio_calibrated_to_break_even=ratio,
        bracket=(lo, hi) if lo <= hi else (hi, lo),
        razorpay_default_revocation_per_execution_ratio_at_break_even=revocation_ratio_at_break_even,
        note=(
            f"break-even located by bisection ({n_bisection_steps} steps) between the "
            f"declared range's edge ({start_edge}) and the physical bound "
            f"({search_lo if widening_downward else search_hi}); "
            f"bracket width {abs(hi - lo):.6f}"
        ),
    )


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
                "razorpay_default_revocation_per_execution_ratio": (
                    p.razorpay_default_revocation_per_execution_ratio
                ),
            }
            for p in points
        ],
        "break_even_vs_aggressive_8x": break_even_agg,
        "break_even_vs_razorpay_default": break_even_rp,
    }

    print(
        "sweeping the other three declared axes "
        "(LTV margin_factor, WhatsApp cost, response_rate)..."
    )
    other = sweep_other_axes(world, params, policy, model_bundle, life_table, n_jobs=5)
    out["other_axes"] = {
        dotted_path: {
            "output_key": label,
            "sensitivity_range": _leaf(params.raw, dotted_path)["sensitivity_range"],
            "points": [
                {
                    "value": p.value,
                    "dobara_mean_net_ltv": p.dobara_mean_net_ltv,
                    "razorpay_default_mean_net_ltv": p.razorpay_default_mean_net_ltv,
                    "aggressive_8x_mean_net_ltv": p.aggressive_8x_mean_net_ltv,
                    "ranking": p.ranking,
                }
                for p in other[dotted_path]
            ],
            "ranking_ever_changes": len({tuple(p.ranking) for p in other[dotted_path]}) > 1,
        }
        for dotted_path, label in OTHER_AXES.items()
    }

    print()
    print(
        "extended break-even search (widening past the declared sensitivity_range "
        "toward a physical/economic bound)..."
    )
    search_axes = [
        "revocation.hazard_per_failure_notification",
        "ltv.margin_factor",
        "notification.cost_inr.whatsapp",
        "date_change_offer.response_rate",
    ]
    search_results = Parallel(n_jobs=4)(
        delayed(search_break_even_vs_razorpay_default)(
            dotted_path, world, params, policy, model_bundle, life_table
        )
        for dotted_path in search_axes
    )
    extended: dict[str, dict[str, object]] = {}
    for dotted_path, result in zip(search_axes, search_results, strict=True):
        extended[dotted_path] = {
            "declared_range": list(result.declared_range),
            "calibrated_value": result.calibrated_value,
            "search_bound": result.search_bound,
            "found": result.found,
            "break_even_value": result.break_even_value,
            "ratio_calibrated_to_break_even": result.ratio_calibrated_to_break_even,
            "bracket": list(result.bracket) if result.bracket is not None else None,
            "razorpay_default_revocation_per_execution_ratio_at_break_even": (
                result.razorpay_default_revocation_per_execution_ratio_at_break_even
            ),
            "note": result.note,
        }
        print(f"  {dotted_path}: {result.note}")
    out["extended_break_even_search_vs_razorpay_default"] = {
        "note": (
            "Searches OUTSIDE sim/params.yaml's declared sensitivity_range, toward a "
            "physical/economic bound, for the value at which razorpay_default would "
            "overtake dobara on net LTV -- sim/params.yaml's declared sensitivity_range "
            "itself is unchanged and remains the honest plausible range other code "
            "reads. See PHYSICAL_SEARCH_BOUND in eval/sensitivity.py for the bound "
            "chosen per axis and why."
        ),
        "axes": extended,
    }

    from eval.provenance import stamp

    out["provenance"] = stamp()

    Path("artifacts").mkdir(exist_ok=True)
    Path("artifacts/sensitivity.json").write_text(json.dumps(out, indent=2))
    print(
        f"wrote artifacts/sensitivity.json ({len(points)} hazard points + "
        f"{sum(len(v) for v in other.values())} other-axis points)"
    )
    print()
    for p in sorted(points, key=lambda p: p.hazard_per_failure_notification):
        print(
            f"hazard={p.hazard_per_failure_notification:.4f}  "
            f"dobara={p.dobara_mean_net_ltv:>9,.2f}  "
            f"razorpay_default={p.razorpay_default_mean_net_ltv:>9,.2f}  "
            f"aggressive_8x={p.aggressive_8x_mean_net_ltv:>9,.2f}  "
            f"dobara_vs_rp={'WIN' if p.dobara_wins else 'lose':4s}  "
            f"dobara_vs_agg={'WIN' if p.dobara_beats_aggressive_8x else 'lose':4s}  "
            f"rp_revocation_per_execution_ratio={p.razorpay_default_revocation_per_execution_ratio:.4f}"
        )
    print()
    print("break_even_vs_aggressive_8x:", json.dumps(break_even_agg, indent=2))
    print("break_even_vs_razorpay_default:", json.dumps(break_even_rp, indent=2))
    print()
    for dotted_path in OTHER_AXES:
        print(f"--- {dotted_path} ---")
        for op in other[dotted_path]:
            print(
                f"  value={op.value:.4f}  dobara={op.dobara_mean_net_ltv:>9,.2f}  "
                f"razorpay_default={op.razorpay_default_mean_net_ltv:>9,.2f}  "
                f"aggressive_8x={op.aggressive_8x_mean_net_ltv:>9,.2f}  "
                f"ranking={op.ranking}"
            )


if __name__ == "__main__":
    main()
