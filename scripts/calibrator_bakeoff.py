"""Investigation only, per `docs/DECISIONS.md` [2026-09-01] "Pre-registration: calibrator
bake-off". Compares four probability calibrators for Model 1 (recovery) against the
committed isotonic baseline (`artifacts/models/recovery_lgbm_calibrator_e5eaa66718f2.joblib`),
fit and evaluated on the EXISTING train/validate splits only. The test set (cycle 6-8) is
never touched here — `artifacts/recovery_model_report.json`'s `n_test_evaluations` stays
at 1.

Writes `artifacts/calibrator_bakeoff.json`. Does not retrain, does not touch `agent/`,
`eval/`, `sim/`, or the README, and does not run `make eval`. See the pre-registered
adoption rule in `docs/DECISIONS.md` before reading the printed summary's conclusion.
"""

from __future__ import annotations

import dataclasses
import json
from datetime import datetime, timedelta
from typing import Any

import numpy as np
import pandas as pd
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from scipy.interpolate import PchipInterpolator

from agent.compliance import is_hard_compliant
from agent.decide import _generate_candidates, _score_all
from agent.models import load_model_bundle
from agent.policy import load_policy
from agent.context import DecisionContext
from eval.provenance import content_hash, stamp
from eval.world import build_world
from features.recovery import LABEL_COLUMN, build_recovery_features
from models.metrics import MIN_SLICE_N, RNG_SEED, bootstrap_ci
from models.recovery import _lgbm_frame, load_recovery_model
from sim.params import load_params

DB_PATH = "data/dobara.sqlite3"
ARTIFACTS_DIR = "artifacts"
MODEL_VERSION = "e5eaa66718f2"
EPS = 1e-6
N_TIE_MANDATES = 300
CYCLE_LENGTH_DAYS = 30
METHOD = "upi_autopay"
BASE_DATE = datetime(2026, 1, 1)


# --- Calibrator wrappers: each exposes .predict(raw) -> calibrated prob, matching
# IsotonicRegression's interface, so they're drop-in swaps for
# TrainedRecoveryModel.lgbm_calibrator without touching agent/decide.py or models/recovery.py. ---


class _IsotonicWrap:
    def __init__(self, raw: np.ndarray, y: np.ndarray) -> None:
        self._m = IsotonicRegression(out_of_bounds="clip").fit(raw, y)

    def predict(self, x: np.ndarray) -> np.ndarray:
        return np.asarray(self._m.predict(x))


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


class _MonotoneSplineWrap:
    """Isotonic's own fitted knots, interpolated with a monotone (PCHIP) spline instead
    of isotonic's own flat step function between them — the same knot placement, smoothed
    rather than staircased, so it can't invent monotonicity violations isotonic didn't
    already imply."""

    def __init__(self, raw: np.ndarray, y: np.ndarray) -> None:
        iso = IsotonicRegression(out_of_bounds="clip").fit(raw, y)
        x = np.asarray(iso.X_thresholds_)
        yv = np.asarray(iso.y_thresholds_)
        ux, idx = np.unique(x, return_index=True)
        uy = yv[idx]
        if len(ux) < 2:
            self._m = None
            self._const = float(uy[0]) if len(uy) else 0.5
        else:
            self._m = PchipInterpolator(ux, uy, extrapolate=False)
            self._lo, self._hi = ux[0], ux[-1]
            self._ylo, self._yhi = uy[0], uy[-1]

    def predict(self, x: np.ndarray) -> np.ndarray:
        x = np.asarray(x, dtype=float)
        if self._m is None:
            return np.full_like(x, self._const, dtype=float)
        out = self._m(np.clip(x, self._lo, self._hi))
        return np.clip(out, 0.0, 1.0)


def _brier(y_true: np.ndarray, y_prob: np.ndarray) -> float:
    return float(np.mean((y_true - y_prob) ** 2))


def _brier_climatology(y_true: np.ndarray) -> float:
    rate = float(np.mean(y_true))
    return _brier(y_true, np.full_like(y_true, rate, dtype=float))


def _distinct_output_values(calibrator: Any, raw_lo: float, raw_hi: float, n: int = 5000) -> int:
    grid = np.linspace(raw_lo, raw_hi, n)
    preds = np.asarray(calibrator.predict(grid))
    return int(len(np.unique(np.round(preds, 8))))


def _build_tie_ctxs(n: int) -> tuple[list[DecisionContext], Any]:
    """Realistic candidate sets, built with the same population-generation function
    (`eval.world.build_world`) and `DecisionContext` field convention `eval/runner.py`'s
    live `dobara` arm uses — first attempt of a mandate's first cycle, no prior history,
    so the comparison is to the committed 76% figure's own methodology, not a synthetic
    probe."""
    params = load_params()
    world = build_world(params, seed=RNG_SEED, n_customers=n)
    ctxs = []
    for m in world.mandates:
        due_date = BASE_DATE + timedelta(days=(m.cycle_day - 1))
        cycle_end = due_date + timedelta(days=CYCLE_LENGTH_DAYS)
        ctxs.append(
            DecisionContext(
                mandate_id=m.mandate_id,
                cycle_id=1,
                cycle_index=1,
                merchant_category=m.merchant_category,
                bank_id=m.customer.bank_id,
                method=METHOD,
                amount=m.amount,
                afa_threshold_applicable=m.amount > float(params.get("afa.threshold_inr")),
                now=due_date,
                cycle_due_date=due_date,
                cycle_end=cycle_end,
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
        )
    return ctxs, params


def _tie_rate(calibrator: Any) -> dict[str, Any]:
    """Reuses `agent/decide.py`'s own `_generate_candidates` / compliance gate /
    `_score_all` unmodified — only the recovery model's calibrator is swapped, via
    `dataclasses.replace` on the loaded `TrainedRecoveryModel`, matching the convention
    `agent/decide.py::_tie_break_score`'s docstring diagnosed the original 76% figure
    with."""
    bundle = load_model_bundle(DB_PATH, ARTIFACTS_DIR)
    swapped_recovery = dataclasses.replace(bundle.recovery, lgbm_calibrator=calibrator)
    bundle = dataclasses.replace(bundle, recovery=swapped_recovery)
    policy = load_policy()

    ctxs, _ = _build_tie_ctxs(N_TIE_MANDATES)
    n_with_alternatives = 0
    n_tied = 0
    for ctx in ctxs:
        candidates = _generate_candidates(ctx, policy)
        legal = [a for a in candidates if is_hard_compliant(a, ctx, policy)]
        if len(legal) < 2:
            continue
        scores = _score_all(legal, ctx, bundle)
        nets = [round(s.expected_net, 6) for s in scores]
        best = max(nets)
        n_with_alternatives += 1
        if nets.count(best) > 1:
            n_tied += 1

    rate = n_tied / n_with_alternatives if n_with_alternatives else float("nan")
    return {
        "n_decisions_with_alternatives": n_with_alternatives,
        "n_tied_at_argmax": n_tied,
        "tie_rate": rate,
    }


def _candidate_report(
    name: str,
    calibrator: Any,
    raw_val_eval: np.ndarray,
    y_val_eval: np.ndarray,
    raw_lo: float,
    raw_hi: float,
) -> dict[str, Any]:
    probs = np.asarray(calibrator.predict(raw_val_eval))
    brier_point, brier_lo, brier_hi = bootstrap_ci(y_val_eval, probs, _brier)
    clim = _brier_climatology(y_val_eval)
    bss = 1.0 - brier_point / clim if clim > 0 else float("nan")
    return {
        "brier_score": {"point": brier_point, "ci_lo": brier_lo, "ci_hi": brier_hi},
        "brier_skill_score_vs_climatology": bss,
        "n_distinct_output_values": _distinct_output_values(calibrator, raw_lo, raw_hi),
        "tie_rate": _tie_rate(calibrator),
    }


def main() -> None:
    df = build_recovery_features(DB_PATH)
    val = df[df["split"] == "validate"]
    y_val = val[LABEL_COLUMN].to_numpy()

    baseline_model = load_recovery_model(MODEL_VERSION, f"{ARTIFACTS_DIR}/models")
    raw_val = np.asarray(baseline_model.lgbm_booster.predict(_lgbm_frame(val)))

    # Split the validate split itself, so each candidate's Brier score is evaluated on
    # data it was not fit on — fitting AND scoring a highly flexible calibrator (isotonic
    # especially) on the identical rows would understate its true error and bias the
    # bake-off toward the most flexible candidate, defeating the comparison's purpose.
    idx = np.arange(len(val))
    idx_fit, idx_eval = train_test_split(
        idx, test_size=0.5, random_state=RNG_SEED, stratify=y_val
    )
    raw_fit, y_fit = raw_val[idx_fit], y_val[idx_fit]
    raw_eval, y_eval = raw_val[idx_eval], y_val[idx_eval]
    raw_lo, raw_hi = float(raw_val.min()), float(raw_val.max())

    candidates: dict[str, Any] = {
        "isotonic_baseline": _IsotonicWrap(raw_fit, y_fit),
        "platt_logistic": _PlattWrap(raw_fit, y_fit),
        "beta_calibration": _BetaWrap(raw_fit, y_fit),
        "monotone_spline": _MonotoneSplineWrap(raw_fit, y_fit),
    }

    report: dict[str, Any] = {
        "n_validate_total": int(len(val)),
        "n_validate_fit": int(len(idx_fit)),
        "n_validate_eval": int(len(idx_eval)),
        "raw_score_range": [raw_lo, raw_hi],
        "candidates": {},
    }
    for name, cal in candidates.items():
        report["candidates"][name] = _candidate_report(name, cal, raw_eval, y_eval, raw_lo, raw_hi)

    baseline = report["candidates"]["isotonic_baseline"]
    verdict: dict[str, Any] = {"per_candidate": {}}
    for name, res in report["candidates"].items():
        if name == "isotonic_baseline":
            continue
        b_lo, b_hi = res["brier_score"]["ci_lo"], res["brier_score"]["ci_hi"]
        base_lo, base_hi = baseline["brier_score"]["ci_lo"], baseline["brier_score"]["ci_hi"]
        ci_overlaps = not (b_hi < base_lo or base_hi < b_lo)
        base_tie = baseline["tie_rate"]["tie_rate"]
        cand_tie = res["tie_rate"]["tie_rate"]
        halves_tie_rate = cand_tie <= base_tie / 2 if base_tie == base_tie else False  # NaN-safe
        verdict["per_candidate"][name] = {
            "criterion_a_brier_ci_overlaps_isotonic": ci_overlaps,
            "criterion_b_tie_rate_at_least_halved": halves_tie_rate,
            "adopt": bool(ci_overlaps and halves_tie_rate),
        }
    verdict["any_candidate_meets_both_criteria"] = any(
        v["adopt"] for v in verdict["per_candidate"].values()
    )
    report["pre_registered_verdict"] = verdict
    report["provenance"] = stamp()
    report["content_hash"] = content_hash(
        {k: v for k, v in report.items() if k != "provenance"}
    )

    out_path = f"{ARTIFACTS_DIR}/calibrator_bakeoff.json"
    with open(out_path, "w") as f:
        json.dump(report, f, indent=2)

    print(f"wrote {out_path}\n")
    print(f"isotonic baseline: Brier {baseline['brier_score']['point']:.4f} "
          f"[{baseline['brier_score']['ci_lo']:.4f}, {baseline['brier_score']['ci_hi']:.4f}], "
          f"{baseline['n_distinct_output_values']} distinct values, "
          f"tie rate {baseline['tie_rate']['tie_rate']:.1%}")
    for name, res in report["candidates"].items():
        if name == "isotonic_baseline":
            continue
        v = verdict["per_candidate"][name]
        print(f"\n{name}: Brier {res['brier_score']['point']:.4f} "
              f"[{res['brier_score']['ci_lo']:.4f}, {res['brier_score']['ci_hi']:.4f}], "
              f"{res['n_distinct_output_values']} distinct values, "
              f"tie rate {res['tie_rate']['tie_rate']:.1%}")
        print(f"  (a) Brier CI overlaps isotonic: {v['criterion_a_brier_ci_overlaps_isotonic']}")
        print(f"  (b) tie rate at least halved:   {v['criterion_b_tie_rate_at_least_halved']}")
        print(f"  adopt under pre-registered rule: {v['adopt']}")

    print(f"\nAny candidate meets both pre-registered criteria: "
          f"{verdict['any_candidate_meets_both_criteria']}")
    if verdict["any_candidate_meets_both_criteria"]:
        print("Per the pre-registered rule (docs/DECISIONS.md [2026-09-01]), this would "
              "warrant adopting a replacement and rerunning `make eval` — NOT done by "
              "this script; report and stop, per instructions.")
    else:
        print("Per the pre-registered rule (docs/DECISIONS.md [2026-09-01]), this is a "
              "NEGATIVE RESULT: isotonic stays, the coarseness is a named, measured, "
              "documented limitation, not silently fixed.")


if __name__ == "__main__":
    main()
