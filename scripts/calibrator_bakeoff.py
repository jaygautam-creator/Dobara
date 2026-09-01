"""Investigation only, per `docs/DECISIONS.md` [2026-09-01] "Pre-registration: calibrator
bake-off". Compares four probability calibrators for Model 1 (recovery) against the
committed isotonic baseline (`artifacts/models/recovery_lgbm_calibrator_e5eaa66718f2.joblib`),
fit and evaluated on the EXISTING train/validate splits only. The test set (cycle 6-8) is
never touched here — `artifacts/recovery_model_report.json`'s `n_test_evaluations` stays
at 1.

Writes `artifacts/calibrator_bakeoff.json`. Does not retrain, does not touch `agent/`,
`eval/`, `sim/`, or the README, and does not run `make eval`. See the pre-registered
adoption rule in `docs/DECISIONS.md` before reading the printed summary's conclusion.

**2026-09-01 follow-up (same script, extended, adoption question NOT reopened):**
resolves a number collision (this script's own isotonic tie rate vs. the committed 76%
figure — see `POPULATION` below and `docs/DECISIONS.md` [2026-09-01] "Number collision
resolved") and decomposes the remaining tie rate into raw-model-score ties (upstream of
any calibrator) versus calibrator-added ties (`docs/DECISIONS.md` [2026-09-01] "Raw-score
tie decomposition").
"""

from __future__ import annotations

import dataclasses
import json
from datetime import datetime, timedelta
from typing import Any

import numpy as np
from scipy.interpolate import PchipInterpolator
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split

from agent.actions import ScheduleDebit
from agent.audit import AuditTrail
from agent.compliance import is_hard_compliant
from agent.context import DecisionContext
from agent.decide import _generate_candidates, _score_all
from agent.models import load_model_bundle
from agent.policy import load_policy
from eval.arms import Arm
from eval.provenance import content_hash, stamp
from eval.runner import run_arm
from eval.world import build_world
from features.recovery import LABEL_COLUMN, build_recovery_features
from models.ltv import build_life_table
from models.metrics import RNG_SEED, bootstrap_ci
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

# The population this script's own tie-rate figure is measured over, per
# docs/DECISIONS.md [2026-09-01] "Number collision resolved": every mandate's FIRST
# cycle (cycle_index=1), FIRST attempt (attempt_index=1), zero prior history — built
# from `eval.world.build_world` at the TRAINING seed (`RNG_SEED`=42, same population
# `data/dobara.sqlite3` was trained on, not a held-out eval seed). This is deliberately
# narrower than the committed demo fixture's 76% figure, which is measured over EVERY
# decision with alternatives across a mandate's full multi-cycle lifecycle on a
# held-out eval-world population (seed 9001, `api/demo.py::DEMO_SEED`). The two numbers
# answer different questions; see `POPULATION_RECONCILIATION` below for a same-code,
# apples-to-apples reproduction of both, on the SAME (production, unmodified) calibrator.
POPULATION: dict[str, Any] = {
    "description": (
        "Every mandate's first cycle (cycle_index=1), first attempt (attempt_index=1), "
        "zero prior history -- NOT the same population as the committed 76% figure "
        "(docs/DECISIONS.md [2026-08-27]), which spans every decision with alternatives "
        "across a mandate's full multi-cycle lifecycle. See "
        "'population_reconciliation' for a direct, same-code comparison of both."
    ),
    "cycle_index": 1,
    "attempt_index": 1,
    "world_seed": RNG_SEED,
    "world_seed_note": (
        "same seed as the recovery model's own training population, not a held-out eval seed"
    ),
    "n_mandates": N_TIE_MANDATES,
}

# The committed demo fixture's population, for the reconciliation run below --
# api/demo.py::DEMO_SEED / DEMO_N_CUSTOMERS, a held-out eval-world population.
DEMO_SEED = 9001
DEMO_N_CUSTOMERS = 150

# Date-derived features that vary across candidate dates *within one decision* -- the
# only features that can possibly cause or avoid a within-decision tie. `day_of_week`
# is on this list even though the booster never splits on it (confirmed below) because
# it's the feature the original 2026-08-27 diagnosis and this codebase's date-signal
# story is framed around.
DATE_FEATURES = [
    "day_of_month",
    "day_of_week",
    "bank_dow_profile",
    "days_until_cycle_end",
    "is_month_start_window",
    "is_mid_month_window",
]


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
        return np.asarray(np.clip(out, 0.0, 1.0))


class _IdentityWrap:
    """No calibration at all -- the raw booster score, clipped to `[0, 1]`. Swapped in
    exactly like every other candidate (via `dataclasses.replace` on
    `TrainedRecoveryModel.lgbm_calibrator` in `_tie_rate`) so its argmax tie rate
    measures ties that exist in the raw model output itself, upstream of any
    calibration step -- Job 2's "raw-score tie rate"."""

    def predict(self, x: np.ndarray) -> np.ndarray:
        return np.asarray(np.clip(np.asarray(x, dtype=float), 0.0, 1.0))


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
    live `dobara` arm uses — first attempt of a mandate's FIRST CYCLE ONLY, no prior
    history. Real candidate construction (`agent.decide._generate_candidates`), real
    compliance gate, real scoring — but **not the same population as the committed 76%
    figure**, which spans a mandate's full multi-cycle lifecycle (see `POPULATION` above
    and `docs/DECISIONS.md` [2026-09-01] "Number collision resolved" for the measured
    gap this causes, and `_population_reconciliation` for a direct, same-code
    comparison)."""
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


def _tie_rate(
    calibrator: Any, ctxs: list[DecisionContext] | None = None, track_raw_diversity: bool = False
) -> dict[str, Any]:
    """Reuses `agent/decide.py`'s own `_generate_candidates` / compliance gate /
    `_score_all` unmodified — only the recovery model's calibrator is swapped, via
    `dataclasses.replace` on the loaded `TrainedRecoveryModel`, matching the convention
    `agent/decide.py::_tie_break_score`'s docstring diagnosed the original 76% figure
    with. Population is `POPULATION` (see module docstring) unless an explicit `ctxs`
    list is passed (used by the reconciliation run below, over a different
    population)."""
    bundle = load_model_bundle(DB_PATH, ARTIFACTS_DIR)
    swapped_recovery = dataclasses.replace(bundle.recovery, lgbm_calibrator=calibrator)
    bundle = dataclasses.replace(bundle, recovery=swapped_recovery)
    policy = load_policy()

    if ctxs is None:
        ctxs, _ = _build_tie_ctxs(N_TIE_MANDATES)
    n_with_alternatives = 0
    n_tied = 0
    distinct_raw_counts: list[int] = []
    n_schedule_debit_counts: list[int] = []
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
        if track_raw_diversity:
            sd_idx = [i for i, a in enumerate(legal) if isinstance(a, ScheduleDebit)]
            if sd_idx:
                raws = {round(scores[i].rupee_math.p_success, 8) for i in sd_idx}
                distinct_raw_counts.append(len(raws))
                n_schedule_debit_counts.append(len(sd_idx))

    rate = n_tied / n_with_alternatives if n_with_alternatives else float("nan")
    result: dict[str, Any] = {
        "n_decisions_with_alternatives": n_with_alternatives,
        "n_tied_at_argmax": n_tied,
        "tie_rate": rate,
    }
    if track_raw_diversity and distinct_raw_counts:
        result["mean_scheduledebit_candidates_per_decision"] = float(
            np.mean(n_schedule_debit_counts)
        )
        result["mean_distinct_raw_p_success_per_decision"] = float(np.mean(distinct_raw_counts))
        # Per CANDIDATE (day x channel; `mean_scheduledebit_candidates_per_decision`
        # above), not per day -- channel doesn't affect `p_success`, so this
        # undercounts true per-day resolution, but it's the ratio these two fields
        # actually compute and it must be readable back from them without ambiguity.
        result["mean_raw_score_resolution_per_candidate"] = float(
            np.mean(np.array(distinct_raw_counts) / np.array(n_schedule_debit_counts))
        )
    return result


def _date_feature_split_analysis(booster: Any) -> dict[str, Any]:
    """Job 2 step 2: does the trained booster actually split on the date-derived
    features that vary across one decision's candidate set, and at what granularity?
    Directly inspects the persisted booster (`artifacts/models/recovery_lgbm_*.joblib`)
    — no retraining."""
    names = list(booster.feature_name())
    gain = booster.feature_importance(importance_type="gain")
    split_count = booster.feature_importance(importance_type="split")
    trees = booster.trees_to_dataframe()

    # Computed once, here, from the booster's own gain array -- never hand-copied into
    # prose, so a rank claim in the README/DECISIONS.md can be checked against this
    # field instead of drifting from it (this is the fix for the 2026-09-01 "third- vs
    # fourth-highest-gain" correction: `day_of_month` is rank 4, not 3).
    gain_order = np.argsort(-gain)
    rank_by_name = {names[i]: int(r) + 1 for r, i in enumerate(gain_order)}

    out: dict[str, Any] = {}
    for feat in DATE_FEATURES:
        idx = names.index(feat) if feat in names else None
        rows = trees[trees["split_feature"] == feat]
        thresholds = sorted({round(float(t), 4) for t in rows["threshold"].dropna()})
        out[feat] = {
            "gain": float(gain[idx]) if idx is not None else 0.0,
            "gain_rank_among_all_features": rank_by_name.get(feat),
            "n_features_total": len(names),
            "split_count": int(split_count[idx]) if idx is not None else 0,
            "n_distinct_thresholds_in_forest": len(thresholds),
            "thresholds_sample": thresholds[:10],
        }
    return out


def _population_reconciliation() -> dict[str, Any]:
    """Job 1: reproduces BOTH the committed 76% figure's methodology and this script's
    own narrower `POPULATION` on the SAME code path and the SAME (unmodified,
    production) calibrator, so the two published numbers can be directly compared
    rather than argued about. Runs the live `dobara` arm once (held-out eval world,
    `DEMO_SEED`/`DEMO_N_CUSTOMERS` — the same population `api/demo.py` uses to build the
    committed demo fixture) with an `AuditTrail`, then recomputes the argmax tie
    directly from each recorded decision's own `ctx` via `_generate_candidates`/
    `is_hard_compliant`/`_score_all` (not from the fixture's already-collapsed
    `rejected_alternatives` lists, so this is a from-scratch reproduction, not a
    re-read)."""
    params = load_params()
    policy = load_policy()
    bundle = load_model_bundle(DB_PATH, ARTIFACTS_DIR)
    life_table = build_life_table(DB_PATH, int(params.get("ltv.horizon_cycles")))
    world = build_world(params, seed=DEMO_SEED, n_customers=DEMO_N_CUSTOMERS)

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

    def _tie_over(
        recs: list[Any], model_bundle: Any = bundle, track_raw_diversity: bool = False
    ) -> dict[str, Any]:
        n_with = 0
        n_tied = 0
        distinct_raw_counts: list[int] = []
        n_schedule_debit_counts: list[int] = []
        for r in recs:
            ctx = r.ctx
            candidates = _generate_candidates(ctx, policy)
            legal = [a for a in candidates if is_hard_compliant(a, ctx, policy)]
            if len(legal) < 2:
                continue
            scores = _score_all(legal, ctx, model_bundle)
            nets = [round(s.expected_net, 6) for s in scores]
            best = max(nets)
            n_with += 1
            if nets.count(best) > 1:
                n_tied += 1
            if track_raw_diversity:
                sd_idx = [i for i, a in enumerate(legal) if isinstance(a, ScheduleDebit)]
                if sd_idx:
                    raws = {round(scores[i].rupee_math.p_success, 8) for i in sd_idx}
                    distinct_raw_counts.append(len(raws))
                    n_schedule_debit_counts.append(len(sd_idx))
        rate = n_tied / n_with if n_with else float("nan")
        result: dict[str, Any] = {
            "n_decisions_with_alternatives": n_with,
            "n_tied_at_argmax": n_tied,
            "tie_rate": rate,
        }
        if track_raw_diversity and distinct_raw_counts:
            result["mean_scheduledebit_candidates_per_decision"] = float(
                np.mean(n_schedule_debit_counts)
            )
            result["mean_distinct_raw_p_success_per_decision"] = float(np.mean(distinct_raw_counts))
            result["mean_raw_score_resolution_per_candidate"] = float(
                np.mean(np.array(distinct_raw_counts) / np.array(n_schedule_debit_counts))
            )
        return result

    all_decisions = _tie_over(records)
    attempt1_records = [r for r in records if r.ctx.attempt_index == 1]
    attempt1_only = _tie_over(attempt1_records)

    # Held-out-seed raw-score tie decomposition (Job 2, reproduced on seed 9001 rather
    # than only on this script's own training-seed POPULATION) -- same records, same
    # `_generate_candidates`/`_score_all` path, only the calibrator swapped to
    # `_IdentityWrap` (no fitting, raw booster score clipped to [0,1]).
    identity_bundle = dataclasses.replace(
        bundle, recovery=dataclasses.replace(bundle.recovery, lgbm_calibrator=_IdentityWrap())
    )
    raw_score_all_decisions = _tie_over(
        records, model_bundle=identity_bundle, track_raw_diversity=True
    )
    raw_score_attempt1_only = _tie_over(
        attempt1_records, model_bundle=identity_bundle, track_raw_diversity=True
    )

    return {
        "note": (
            "Both figures below use the SAME unmodified production calibrator and the "
            "SAME held-out eval-world population (seed "
            f"{DEMO_SEED}, n={DEMO_N_CUSTOMERS}) `api/demo.py` uses to build the "
            "committed demo fixture. 'all_decisions_with_alternatives' reproduces the "
            "committed 76% figure's methodology (docs/DECISIONS.md [2026-08-27]: every "
            "decision with alternatives, every cycle, every attempt index). "
            "'attempt_index_1_only' isolates just the attempt-index restriction, still "
            "spanning every cycle_index. Neither matches this script's own "
            "cycle_index=1-only POPULATION exactly -- see 'population_effect' below."
        ),
        "all_decisions_with_alternatives": all_decisions,
        "attempt_index_1_only": attempt1_only,
        "held_out_raw_score_tie_decomposition": {
            "note": (
                "Job 2's raw-score-vs-calibrator decomposition, reproduced on the SAME "
                f"held-out eval-world population as above (seed {DEMO_SEED}, "
                f"n={DEMO_N_CUSTOMERS}), not just on POPULATION's training-seed (42) "
                "sample -- so the raw-score tie rate can be read on either seed without "
                "ambiguity about which world it came from."
            ),
            "all_decisions_with_alternatives": raw_score_all_decisions,
            "attempt_index_1_only": raw_score_attempt1_only,
        },
    }


def _candidate_report(
    name: str,
    calibrator: Any,
    raw_val_eval: np.ndarray,
    y_val_eval: np.ndarray,
    raw_lo: float,
    raw_hi: float,
    ctxs: list[DecisionContext],
) -> dict[str, Any]:
    probs = np.asarray(calibrator.predict(raw_val_eval))
    brier_point, brier_lo, brier_hi = bootstrap_ci(y_val_eval, probs, _brier)
    clim = _brier_climatology(y_val_eval)
    bss = 1.0 - brier_point / clim if clim > 0 else float("nan")
    return {
        "brier_score": {"point": brier_point, "ci_lo": brier_lo, "ci_hi": brier_hi},
        "brier_skill_score_vs_climatology": bss,
        "n_distinct_output_values": _distinct_output_values(calibrator, raw_lo, raw_hi),
        "tie_rate": _tie_rate(calibrator, ctxs=ctxs),
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
    idx_fit, idx_eval = train_test_split(idx, test_size=0.5, random_state=RNG_SEED, stratify=y_val)
    raw_fit, y_fit = raw_val[idx_fit], y_val[idx_fit]
    raw_eval, y_eval = raw_val[idx_eval], y_val[idx_eval]
    raw_lo, raw_hi = float(raw_val.min()), float(raw_val.max())

    candidates: dict[str, Any] = {
        "isotonic_baseline": _IsotonicWrap(raw_fit, y_fit),
        "platt_logistic": _PlattWrap(raw_fit, y_fit),
        "beta_calibration": _BetaWrap(raw_fit, y_fit),
        "monotone_spline": _MonotoneSplineWrap(raw_fit, y_fit),
    }

    tie_ctxs, _ = _build_tie_ctxs(N_TIE_MANDATES)

    report: dict[str, Any] = {
        "population": POPULATION,
        "n_validate_total": int(len(val)),
        "n_validate_fit": int(len(idx_fit)),
        "n_validate_eval": int(len(idx_eval)),
        "raw_score_range": [raw_lo, raw_hi],
        "candidates": {},
    }
    for name, cal in candidates.items():
        report["candidates"][name] = _candidate_report(
            name, cal, raw_eval, y_eval, raw_lo, raw_hi, tie_ctxs
        )

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
    verdict["note"] = (
        "This bake-off's adoption question (docs/DECISIONS.md [2026-09-01] "
        "'Pre-registration') is settled and NOT reopened by the 2026-09-01 follow-up "
        "investigation below (number collision / raw-score decomposition). That "
        "investigation is about WHY ties happen, not whether to adopt a different "
        "calibrator -- the pre-registered rule and its NEGATIVE verdict stand as-is."
    )
    report["pre_registered_verdict"] = verdict

    # --- Job 2: raw-score tie decomposition (2026-09-01 follow-up) ---
    raw_tie = _tie_rate(_IdentityWrap(), ctxs=tie_ctxs, track_raw_diversity=True)
    total_tie = baseline["tie_rate"]["tie_rate"]
    n_total_tied = baseline["tie_rate"]["n_tied_at_argmax"]
    n_raw_tied = raw_tie["n_tied_at_argmax"]
    n_calibrator_only_tied = n_total_tied - n_raw_tied
    booster = baseline_model.lgbm_booster
    report["raw_score_tie_decomposition"] = {
        "note": (
            "Decomposes the isotonic_baseline tie rate above into ties that already "
            "exist in the raw (uncalibrated) booster output (upstream of calibration) "
            "versus ties added by the calibrator's own quantization. Measured on the "
            "SAME population/candidates as 'candidates' above."
        ),
        "raw_score_tie_rate": raw_tie,
        "total_tied_at_argmax": n_total_tied,
        "raw_tied_at_argmax": n_raw_tied,
        "calibrator_added_ties": n_calibrator_only_tied,
        "share_of_total_ties_from_raw_score": (
            n_raw_tied / n_total_tied if n_total_tied else float("nan")
        ),
        "share_of_total_ties_from_calibrator": (
            n_calibrator_only_tied / n_total_tied if n_total_tied else float("nan")
        ),
        "date_feature_split_analysis": _date_feature_split_analysis(booster),
    }
    reconciliation = _population_reconciliation()
    # Production (unmodified, full-validate-fit) calibrator on THIS script's own
    # narrower cycle_index=1-only population -- isolates the population-narrowing
    # effect from the separate calibrator-refit-on-half-data effect (baseline above
    # uses `_IsotonicWrap` refit on `raw_fit`/`y_fit`, half the validate split, per the
    # fair-comparison rationale above `train_test_split` -- not the production artifact).
    production_on_script_population = _tie_rate(baseline_model.lgbm_calibrator, ctxs=tie_ctxs)
    reconciliation["population_effect"] = {
        "note": (
            "Same production (unmodified) calibrator throughout -- isolates how much of "
            "the 76%->94% gap is the population narrowing (full multi-cycle demo world "
            "-> this script's cycle_index=1-only, train-seed population) versus the "
            "separate effect of refitting isotonic on half the validate split for the "
            "candidate comparison above."
        ),
        "full_population_all_decisions_production_calibrator": reconciliation[
            "all_decisions_with_alternatives"
        ]["tie_rate"],
        "this_script_population_production_calibrator": production_on_script_population["tie_rate"],
        "this_script_population_refit_half_calibrator": total_tie,
    }
    report["population_reconciliation"] = reconciliation
    report["provenance"] = stamp()
    report["content_hash"] = content_hash({k: v for k, v in report.items() if k != "provenance"})

    out_path = f"{ARTIFACTS_DIR}/calibrator_bakeoff.json"
    with open(out_path, "w") as f:
        json.dump(report, f, indent=2)

    print(f"wrote {out_path}\n")
    print(
        f"isotonic baseline: Brier {baseline['brier_score']['point']:.4f} "
        f"[{baseline['brier_score']['ci_lo']:.4f}, {baseline['brier_score']['ci_hi']:.4f}], "
        f"{baseline['n_distinct_output_values']} distinct values, "
        f"tie rate {baseline['tie_rate']['tie_rate']:.1%}"
    )
    for name, res in report["candidates"].items():
        if name == "isotonic_baseline":
            continue
        v = verdict["per_candidate"][name]
        print(
            f"\n{name}: Brier {res['brier_score']['point']:.4f} "
            f"[{res['brier_score']['ci_lo']:.4f}, {res['brier_score']['ci_hi']:.4f}], "
            f"{res['n_distinct_output_values']} distinct values, "
            f"tie rate {res['tie_rate']['tie_rate']:.1%}"
        )
        print(f"  (a) Brier CI overlaps isotonic: {v['criterion_a_brier_ci_overlaps_isotonic']}")
        print(f"  (b) tie rate at least halved:   {v['criterion_b_tie_rate_at_least_halved']}")
        print(f"  adopt under pre-registered rule: {v['adopt']}")

    print(
        f"\nAny candidate meets both pre-registered criteria: "
        f"{verdict['any_candidate_meets_both_criteria']}"
    )
    if verdict["any_candidate_meets_both_criteria"]:
        print(
            "Per the pre-registered rule (docs/DECISIONS.md [2026-09-01]), this would "
            "warrant adopting a replacement and rerunning `make eval` — NOT done by "
            "this script; report and stop, per instructions."
        )
    else:
        print(
            "Per the pre-registered rule (docs/DECISIONS.md [2026-09-01]), this is a "
            "NEGATIVE RESULT: isotonic stays, the coarseness is a named, measured, "
            "documented limitation, not silently fixed. NOT reopened by the analysis "
            "below."
        )

    dec = report["raw_score_tie_decomposition"]
    raw_tr = dec["raw_score_tie_rate"]
    n_with_alt = baseline["tie_rate"]["n_decisions_with_alternatives"]
    resolution = raw_tr.get("mean_raw_score_resolution_per_candidate", float("nan"))
    print(
        f"\n--- Job 2: raw-score tie decomposition "
        f"(population: {POPULATION['description'][:60]}...) ---"
    )
    print(
        f"raw-score (uncalibrated) tie rate: {raw_tr['tie_rate']:.1%} "
        f"({dec['raw_tied_at_argmax']}/{raw_tr['n_decisions_with_alternatives']})"
    )
    print(f"isotonic (total) tie rate: {total_tie:.1%} ({n_total_tied}/{n_with_alt})")
    print(
        f"of {n_total_tied} total ties: {n_raw_tied} "
        f"({dec['share_of_total_ties_from_raw_score']:.1%}) already tied in raw score; "
        f"{n_calibrator_only_tied} ({dec['share_of_total_ties_from_calibrator']:.1%}) "
        f"added by calibrator quantization"
    )
    print(
        f"mean raw-score resolution: {resolution:.1%} of ScheduleDebit CANDIDATES "
        f"(day x channel) get a distinct raw score -- population n=300, world_seed=42 "
        f"(the recovery model's OWN TRAINING seed, not held-out; see "
        f"'held_out_raw_score_tie_decomposition' below for the seed-9001 reproduction)"
    )
    feats = dec["date_feature_split_analysis"]
    dom_rank = feats["day_of_month"]["gain_rank_among_all_features"]
    n_feat = feats["day_of_month"]["n_features_total"]
    print(
        f"\nday_of_month gain rank: {dom_rank}/{n_feat} (computed from the booster's own "
        f"gain array, not hand-copied)"
    )
    print(
        f"day_of_week booster splits: {feats['day_of_week']['split_count']}"
        f" | day_of_month splits: {feats['day_of_month']['split_count']}"
        f" | bank_dow_profile splits: {feats['bank_dow_profile']['split_count']}"
    )

    rec = report["population_reconciliation"]
    print("\n--- Job 1: population reconciliation (same code, same production calibrator) ---")
    n_all = rec["all_decisions_with_alternatives"]["n_decisions_with_alternatives"]
    print(
        f"full demo-fixture-style population (n={n_all}, held-out world_seed={DEMO_SEED}), "
        f"all decisions: {rec['all_decisions_with_alternatives']['tie_rate']:.1%} "
        f"(committed 76% figure's own methodology)"
    )
    print(
        f"same held-out population, attempt_index==1 only "
        f"(n={rec['attempt_index_1_only']['n_decisions_with_alternatives']}): "
        f"{rec['attempt_index_1_only']['tie_rate']:.1%}"
    )
    print(
        "this script's own cycle_index==1-only, world_seed=42 population (production "
        "calibrator): see 'population_effect' note in artifacts/calibrator_bakeoff.json"
    )

    hraw = rec["held_out_raw_score_tie_decomposition"]
    ha = hraw["attempt_index_1_only"]
    print(
        f"\nheld-out (world_seed={DEMO_SEED}) raw-score tie rate, attempt_index==1 only "
        f"(n={ha['n_decisions_with_alternatives']}): {ha['tie_rate']:.1%}"
    )


if __name__ == "__main__":
    main()
