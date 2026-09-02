"""Read-only verification of the claim in the 2026-09-01 follow-up message: that the
pre-registered criterion (b) ("cuts the argmax tie rate by at least half") PASSES for
Platt/beta calibration when measured on the held-out eval world (seed 9001), even though
it FAILED on the n=300 training-seed (seed=42) sample `scripts/calibrator_bakeoff.py`'s
own `main()` evaluates it on.

Two things are checked, both DIRECTLY on the held-out population rather than inferred:
  1. Platt's and beta's own argmax tie rate on held-out world records (not inferred from
     "Platt is a monotone reparametrization of the raw score" — measured, same as
     `_IdentityWrap`'s raw-score tie rate already is in `calibrator_bakeoff.py`).
  2. Criterion (a), the Brier-CI-overlap-with-isotonic check, on the SAME held-out
     population (not just the `validate` split) -- so both pre-registered criteria are
     read off one, common population.

No retraining of the recovery model. No `make eval`. `artifacts/recovery_model_report.json`'s
`n_test_evaluations` is untouched (this script never imports the test split). Platt/beta
calibrators are refit on the SAME half-validate-split fit data
(`raw_fit`/`y_fit`, `random_state=RNG_SEED`) `calibrator_bakeoff.py::main()` already uses
-- this is fitting a calibrator candidate under evaluation, which the pre-registered bake-
off always does; it is not retraining the production recovery model.

For Brier scoring on the held-out population, ground-truth `y` is obtained by
independently re-drawing each ScheduleDebit decision's actual attempt outcome via
`sim.engine.attempt_outcome` keyed through `eval.rng.event_rng(seed, mandate_id,
cycle_index, attempt_index, "outcome")` -- the exact same deterministic, key-based draw
`eval/runner.py::_draw_attempt` uses internally. Because `event_rng` is a pure function of
its key (SHA-256-seeded, no shared stream state -- see `eval/rng.py`'s docstring), this
reproduces bit-for-bit the same outcome `run_arm`'s own DOBARA arm would have drawn for
that decision, without needing to modify `eval/runner.py` to expose it.

Writes `artifacts/calibrator_bakeoff.json["held_out_direct_verification"]` (adds a key,
does not touch any existing key). Prints a plain verdict.
"""

from __future__ import annotations

import dataclasses
import json
from typing import Any

import numpy as np
from sklearn.linear_model import LogisticRegression

from agent.actions import ScheduleDebit
from agent.audit import AuditTrail
from agent.compliance import is_hard_compliant
from agent.decide import _generate_candidates, _score_all
from agent.models import load_model_bundle
from agent.policy import load_policy
from eval.arms import Arm
from eval.provenance import stamp
from eval.rng import event_rng
from eval.world import build_world
from features.recovery import LABEL_COLUMN, build_recovery_features
from models.metrics import RNG_SEED, bootstrap_ci
from models.recovery import _lgbm_frame, load_recovery_model
from sim.engine import attempt_outcome
from sim.params import load_params

# Kept identical to, and not imported from, scripts/calibrator_bakeoff.py -- importing a
# sibling top-level script by dotted path (`scripts.calibrator_bakeoff`) collides with
# mypy's own scan of `scripts/` as top-level modules ("found twice under different
# module names"). Duplicated verbatim rather than restructuring calibrator_bakeoff.py's
# module layout, which is out of scope for a read-only verification script.
DB_PATH = "data/dobara.sqlite3"
ARTIFACTS_DIR = "artifacts"
MODEL_VERSION = "e5eaa66718f2"
EPS = 1e-6
DEMO_SEED = 9001
DEMO_N_CUSTOMERS = 150


class _PlattWrap:
    """Platt scaling: logistic regression on the raw score itself."""

    def __init__(self, raw: np.ndarray, y: np.ndarray) -> None:
        self._m = LogisticRegression()
        self._m.fit(raw.reshape(-1, 1), y)

    def predict(self, x: np.ndarray) -> np.ndarray:
        return np.asarray(self._m.predict_proba(np.asarray(x).reshape(-1, 1))[:, 1])


class _BetaWrap:
    """Beta calibration (Kull et al. 2017): logistic regression on
    [log(p), -log(1-p)] — equivalent to fitting a 2-parameter beta-distribution link."""

    def __init__(self, raw: np.ndarray, y: np.ndarray) -> None:
        self._m = LogisticRegression()
        self._m.fit(self._features(raw), y)

    @staticmethod
    def _features(x: np.ndarray) -> np.ndarray:
        p = np.clip(np.asarray(x, dtype=float), EPS, 1 - EPS)
        return np.column_stack([np.log(p), -np.log(1 - p)])

    def predict(self, x: np.ndarray) -> np.ndarray:
        return np.asarray(self._m.predict_proba(self._features(x))[:, 1])


def _brier(y_true: np.ndarray, y_prob: np.ndarray) -> float:
    return float(np.mean((y_true - y_prob) ** 2))


def _prior_attempt_failed(ctx: Any) -> bool:
    return ctx.attempt_index > 1 and ctx.last_attempt_outcome in ("soft_decline", "hard_decline")


def _draw_ground_truth_outcome(ctx: Any, action: ScheduleDebit, world: Any, params: Any) -> str:
    """Independently reproduces the exact outcome `eval/runner.py::_draw_attempt` would
    have drawn for this decision, from `event_rng`'s key alone -- see module docstring.
    """
    mandate = next(m for m in world.mandates if m.mandate_id == ctx.mandate_id)
    bank = world.banks[mandate.customer.bank_id]
    regime_from_cycle = int(params.get("regime_shift.applies_from_cycle_index"))
    regime_bd_mult = float(params.get("regime_shift.shift_multiplier_bd"))
    bd_mult = (
        regime_bd_mult
        if (mandate.regime_shift_bank and ctx.cycle_index >= regime_from_cycle)
        else 1.0
    )
    draw = attempt_outcome(
        bank,
        mandate.customer,
        action.t,
        ctx.amount,
        True,
        params,
        world.dated_outages,
        event_rng(DEMO_SEED, ctx.mandate_id, ctx.cycle_index, ctx.attempt_index, "outcome"),
        bd_mult,
        _prior_attempt_failed(ctx),
    )
    return draw.outcome


def _tie_and_brier_over(
    records: list[Any],
    world: Any,
    params: Any,
    policy: Any,
    bundle_raw: Any,
    calibrators: dict[str, Any],
) -> dict[str, Any]:
    """For each record: recompute candidates/compliance/scores on the RAW (identity)
    calibrator once to get each ScheduleDebit candidate's raw booster score and to
    determine the argmax tie under each calibrator-under-test via that same raw score
    (a calibrator only reorders/collapses raw scores -- it cannot change which candidates
    exist), and independently draw ground truth for the chosen action's outcome for the
    Brier comparison.
    """
    raw_pairs: list[tuple[float, int]] = []  # (raw p_success of the CHOSEN action, y)
    tie_counts = {name: 0 for name in calibrators}
    n_with_alt = 0
    for r in records:
        ctx = r.ctx
        candidates = _generate_candidates(ctx, policy)
        legal = [a for a in candidates if is_hard_compliant(a, ctx, policy)]
        if len(legal) < 2:
            continue
        raw_scores = _score_all(legal, ctx, bundle_raw)
        n_with_alt += 1
        # Swap the calibrator into the bundle and call the real _score_all (matching
        # calibrator_bakeoff.py's own convention) so ties are read off actual
        # expected_net, not an approximation of it.
        for name, cal in calibrators.items():
            swapped = dataclasses.replace(
                bundle_raw, recovery=dataclasses.replace(bundle_raw.recovery, lgbm_calibrator=cal)
            )
            scores = _score_all(legal, ctx, swapped)
            nets = [round(s.expected_net, 6) for s in scores]
            best = max(nets)
            if nets.count(best) > 1:
                tie_counts[name] += 1

        # Ground truth for the Brier check: only decisions whose ACTUAL chosen action
        # (per the real run, `r.decision.chosen`) is a ScheduleDebit have a bank-side
        # outcome to draw at all.
        chosen = r.decision.chosen
        if isinstance(chosen, ScheduleDebit):
            outcome = _draw_ground_truth_outcome(ctx, chosen, world, params)
            if outcome == "rejected_no_pdn":
                continue
            y = 1 if outcome == "success" else 0
            raw_for_chosen = next(
                (
                    round(s.rupee_math.p_success, 8)
                    for a, s in zip(legal, raw_scores, strict=True)
                    if a == chosen
                ),
                None,
            )
            if raw_for_chosen is not None:
                raw_pairs.append((raw_for_chosen, y))

    result: dict[str, Any] = {
        "n_decisions_with_alternatives": n_with_alt,
        "tie_rate": {
            name: {
                "n_tied_at_argmax": c,
                "tie_rate": c / n_with_alt if n_with_alt else float("nan"),
            }
            for name, c in tie_counts.items()
        },
        "n_ground_truth_outcomes": len(raw_pairs),
    }
    if raw_pairs:
        raw_arr = np.array([p for p, _ in raw_pairs])
        y_arr = np.array([y for _, y in raw_pairs], dtype=float)
        brier: dict[str, Any] = {}
        for name, cal in calibrators.items():
            probs = np.asarray(cal.predict(raw_arr))
            point, lo, hi = bootstrap_ci(y_arr, probs, _brier)
            brier[name] = {"point": point, "ci_lo": lo, "ci_hi": hi}
        result["brier_on_held_out_ground_truth"] = brier
    return result


def main() -> None:
    params = load_params()
    policy = load_policy()
    bundle = load_model_bundle(DB_PATH, ARTIFACTS_DIR)
    baseline_model = load_recovery_model(MODEL_VERSION, f"{ARTIFACTS_DIR}/models")

    # Refit Platt/beta on the SAME fit half of `validate` main() uses -- calibrator
    # candidates under evaluation, not the production recovery model.
    df = build_recovery_features(DB_PATH)
    val = df[df["split"] == "validate"]
    y_val = val[LABEL_COLUMN].to_numpy()
    raw_val = np.asarray(baseline_model.lgbm_booster.predict(_lgbm_frame(val)))
    from sklearn.model_selection import train_test_split

    idx = np.arange(len(val))
    idx_fit, _ = train_test_split(idx, test_size=0.5, random_state=RNG_SEED, stratify=y_val)
    raw_fit, y_fit = raw_val[idx_fit], y_val[idx_fit]

    calibrators = {
        "isotonic_baseline": baseline_model.lgbm_calibrator,  # production, unmodified
        "platt_logistic": _PlattWrap(raw_fit, y_fit),
        "beta_calibration": _BetaWrap(raw_fit, y_fit),
    }

    from eval.provenance import content_hash
    from eval.runner import run_arm

    world = build_world(params, seed=DEMO_SEED, n_customers=DEMO_N_CUSTOMERS)
    from models.ltv import build_life_table

    life_table = build_life_table(DB_PATH, int(params.get("ltv.horizon_cycles")))
    trail = AuditTrail()
    run_arm(
        world,
        Arm.DOBARA,
        params,
        life_table,
        policy=policy,
        model_bundle=bundle,
        holdout_fraction=0.0,
        audit_trail=trail,
    )
    records = list(trail.records())
    attempt1_records = [r for r in records if r.ctx.attempt_index == 1]

    slices = {
        "all_decisions_with_alternatives": records,
        "attempt_index_1_only": attempt1_records,
    }
    out: dict[str, Any] = {
        "note": (
            "Direct (not inferred) held-out measurement, seed="
            f"{DEMO_SEED}, n_mandates={DEMO_N_CUSTOMERS}. Platt/beta calibrators are the "
            "SAME construction (raw_fit/y_fit, half of validate, random_state=RNG_SEED) "
            "calibrator_bakeoff.py::main() already fits -- reused here unmodified, no "
            "retraining. isotonic_baseline is the unmodified production calibrator."
        ),
        "seed": DEMO_SEED,
        "n_mandates": DEMO_N_CUSTOMERS,
        "slices": {},
    }
    for slice_name, recs in slices.items():
        out["slices"][slice_name] = _tie_and_brier_over(
            recs, world, params, policy, bundle, calibrators
        )

    # Pre-registered criteria, applied unchanged, on this population.
    verdict: dict[str, Any] = {}
    for slice_name, res in out["slices"].items():
        base_tie = res["tie_rate"]["isotonic_baseline"]["tie_rate"]
        base_brier = res.get("brier_on_held_out_ground_truth", {}).get("isotonic_baseline")
        per_cand: dict[str, Any] = {}
        for name in ("platt_logistic", "beta_calibration"):
            cand_tie = res["tie_rate"][name]["tie_rate"]
            halves = cand_tie <= base_tie / 2 if base_tie == base_tie else False
            entry: dict[str, Any] = {"criterion_b_tie_rate_at_least_halved": halves}
            if base_brier is not None:
                cand_brier = res["brier_on_held_out_ground_truth"][name]
                overlaps = not (
                    cand_brier["ci_hi"] < base_brier["ci_lo"]
                    or base_brier["ci_hi"] < cand_brier["ci_lo"]
                )
                entry["criterion_a_brier_ci_overlaps_isotonic"] = overlaps
                entry["adopt"] = bool(overlaps and halves)
            per_cand[name] = entry
        verdict[slice_name] = per_cand
    out["pre_registered_verdict_on_held_out_population"] = verdict
    out["provenance"] = stamp()
    out["content_hash"] = content_hash({k: v for k, v in out.items() if k != "provenance"})

    bakeoff_path = f"{ARTIFACTS_DIR}/calibrator_bakeoff.json"
    with open(bakeoff_path) as f:
        report = json.load(f)
    report["held_out_direct_verification"] = out
    with open(bakeoff_path, "w") as f:
        json.dump(report, f, indent=2)

    print(f"wrote held_out_direct_verification into {bakeoff_path}\n")
    for slice_name, res in out["slices"].items():
        print(f"--- slice: {slice_name} (n_with_alt={res['n_decisions_with_alternatives']}) ---")
        for name in ("isotonic_baseline", "platt_logistic", "beta_calibration"):
            tr = res["tie_rate"][name]
            n_alt = res["n_decisions_with_alternatives"]
            print(f"  {name}: tie rate {tr['tie_rate']:.1%} ({tr['n_tied_at_argmax']}/{n_alt})")
        if "brier_on_held_out_ground_truth" in res:
            print(f"  n ground-truth outcomes for Brier: {res['n_ground_truth_outcomes']}")
            for name, b in res["brier_on_held_out_ground_truth"].items():
                print(f"    {name}: Brier {b['point']:.4f} [{b['ci_lo']:.4f}, {b['ci_hi']:.4f}]")
        v = verdict[slice_name]
        for name, entry in v.items():
            print(f"  {name}: {entry}")
        print()


if __name__ == "__main__":
    main()
