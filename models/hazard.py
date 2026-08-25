"""Model 2 — Revocation Hazard. `P(mandate revoked | this soft-decline attempt)`. Per
docs/05-ML-SPEC.md: **this is the model nobody else will build, and it is where the
thesis lives.**

- Discrete-time hazard on person-period data (see `features/hazard.py` for why the
  exposure unit is per-soft-decline-attempt rather than per-calendar-day here).
- LightGBM, isotonic calibration on validation, same calibration-first treatment as
  Model 1 (`models/metrics.py`).
- **Headline interpretable output:** the marginal hazard per additional failure
  notification within a cycle. Reported as grouped mean predicted hazard by
  `failure_notifications_this_cycle`, with the marginal deltas between consecutive counts.
  **This is not independent empirical evidence for the thesis** —
  `hazard_per_failure_notification` is a declared assumption in `sim/params.yaml`, so this
  number shows the model correctly recovers a relationship the simulator was given by
  hand, which validates the model's specification, not the world. See
  `docs/DECISIONS.md` [2026-08-25] and the README's "Circularity and what our numbers can
  and cannot show" section. What supports the thesis is the regulatory mechanism and the
  published NPCI figures (`docs/01-REGULATORY.md`, `docs/04-DATA-MODEL.md`), not this
  fitted number; Phase 4's sensitivity analysis over the full declared range, plus the
  net-LTV comparison against `aggressive_8x`, is the actual empirical case.
- **Survival conversion:** the fitted per-step hazards imply a survival curve —
  `S(k) = prod_{i=0}^{k-1} (1 - hazard(i failures already this cycle))` — the probability a
  mandate survives k consecutive same-cycle failures without being revoked.
- **No LLM import anywhere in this module** — enforced by `tests/test_no_llm_in_money_path.py`.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.isotonic import IsotonicRegression

from features.hazard import HAZARD_FEATURE_COLUMNS, LABEL_COLUMN, build_hazard_features
from models.metrics import MIN_SLICE_N, RNG_SEED, metric_block

CATEGORICAL_COLUMNS = ["amount_band", "method", "merchant_category"]
NUMERIC_COLUMNS = [c for c in HAZARD_FEATURE_COLUMNS if c not in CATEGORICAL_COLUMNS]
MAX_FAILURE_COUNT_REPORTED = 4  # bucket 4+ together — sparse beyond this per fatigue cap


def _lgbm_frame(df: pd.DataFrame) -> pd.DataFrame:
    X = df[HAZARD_FEATURE_COLUMNS].copy()
    for c in CATEGORICAL_COLUMNS:
        X[c] = X[c].astype("category")
    for c in NUMERIC_COLUMNS:
        if X[c].dtype == bool:
            X[c] = X[c].astype(float)
    return X


@dataclass
class TrainedHazardModel:
    """Loadable inference-time wrapper, added in Phase 3 (`agent/models.py`'s
    `ModelBundle`) — Phase 2 only trained and persisted the raw booster/calibrator to
    joblib. Mirrors `models/recovery.py::TrainedRecoveryModel`.
    """

    booster: lgb.Booster
    calibrator: IsotonicRegression
    model_version: str
    feature_columns: list[str] = field(default_factory=lambda: list(HAZARD_FEATURE_COLUMNS))

    def predict(self, df: pd.DataFrame) -> np.ndarray:
        raw = self.booster.predict(_lgbm_frame(df))
        return np.asarray(self.calibrator.predict(raw))

    def predict_contrib(self, df: pd.DataFrame) -> np.ndarray:
        """Per-row SHAP-style feature contributions (LightGBM's native `pred_contrib`),
        mirrors `models/recovery.py::TrainedRecoveryModel.predict_lgbm_contrib` — see its
        docstring.
        """
        return np.asarray(self.booster.predict(_lgbm_frame(df), pred_contrib=True))


def _model_version(df: pd.DataFrame) -> str:
    payload = f"{sorted(HAZARD_FEATURE_COLUMNS)}|{len(df)}|lgbm+isotonic-hazard|v1"
    return hashlib.sha256(payload.encode()).hexdigest()[:12]


def marginal_hazard_by_failure_count(test: pd.DataFrame, y_prob: np.ndarray) -> dict[str, Any]:
    """The headline number: mean predicted hazard grouped by
    `failure_notifications_this_cycle` (bucketed at MAX_FAILURE_COUNT_REPORTED+), plus the
    marginal delta between consecutive counts and the implied survival curve.
    """
    t = test.copy()
    t["_prob"] = y_prob
    t["_bucket"] = np.minimum(t["failure_notifications_this_cycle"], MAX_FAILURE_COUNT_REPORTED)

    by_count: dict[int, dict[str, Any]] = {}
    for k, g in t.groupby("_bucket"):
        by_count[int(k)] = {"n": int(len(g)), "mean_hazard": float(g["_prob"].mean())}

    counts_sorted = sorted(by_count.keys())
    marginal: dict[str, float] = {}
    survival = {0: 1.0}
    for k in counts_sorted:
        if k > 0 and (k - 1) in by_count:
            marginal[f"{k - 1}_to_{k}"] = (
                by_count[k]["mean_hazard"] - by_count[k - 1]["mean_hazard"]
            )
        prev_survival = survival.get(k - 1, 1.0) if k > 0 else 1.0
        hazard_at_k = by_count.get(k, {}).get("mean_hazard", 0.0)
        survival[k] = prev_survival * (1 - hazard_at_k) if k > 0 else 1.0

    return {
        "mean_hazard_by_failure_count": {str(k): v for k, v in by_count.items()},
        "marginal_hazard_deltas": marginal,
        "survival_curve": {str(k): v for k, v in survival.items()},
        "note": (
            "mean_hazard_by_failure_count[k] = average predicted P(revoke | this attempt) "
            "for attempts that are the (k+1)-th failure notification in their cycle "
            f"(bucketed at {MAX_FAILURE_COUNT_REPORTED}+). survival_curve[k] = probability "
            "a mandate survives k consecutive same-cycle failures without revocation, "
            "computed by chaining the fitted per-step hazards."
        ),
    }


def train_hazard_model(
    db_path: str, out_dir: str = "artifacts", n_test_evaluations: int = 1
) -> dict[str, Any]:
    df = build_hazard_features(db_path)
    train = df[df["split"] == "train"]
    val = df[df["split"] == "validate"]
    test = df[df["split"] == "test"]
    cold_start = df[df["split"] == "cold_start"]

    y_train = train[LABEL_COLUMN].to_numpy()
    y_val = val[LABEL_COLUMN].to_numpy()
    y_test = test[LABEL_COLUMN].to_numpy()

    lgbm_train_set = lgb.Dataset(
        _lgbm_frame(train), label=y_train, categorical_feature=CATEGORICAL_COLUMNS
    )
    booster = lgb.train(
        {
            "objective": "binary",
            "metric": "binary_logloss",
            "verbosity": -1,
            "seed": RNG_SEED,
            "num_leaves": 15,
            "min_data_in_leaf": 20,
            "learning_rate": 0.05,
        },
        lgbm_train_set,
        num_boost_round=200,
    )
    val_raw = booster.predict(_lgbm_frame(val))
    calibrator = IsotonicRegression(out_of_bounds="clip").fit(val_raw, y_val)

    test_raw = np.asarray(booster.predict(_lgbm_frame(test)))
    test_calibrated = np.asarray(calibrator.predict(test_raw))

    model_version = _model_version(df)

    report: dict[str, Any] = {
        "model_version": model_version,
        "n_test_evaluations": n_test_evaluations,
        "test_set_touched_note": (
            "The test set (cycle 6-8) must be touched exactly once, at the end. "
            "This counter is the honesty marker required by docs/05-ML-SPEC.md."
        ),
        "n_train": int(len(train)),
        "n_validate": int(len(val)),
        "n_test": int(len(test)),
        "n_cold_start": int(len(cold_start)),
        "calibrated": metric_block(y_test, test_calibrated),
        "uncalibrated": metric_block(y_test, test_raw),
        "headline_marginal_hazard": marginal_hazard_by_failure_count(test, test_calibrated),
        "slices": _slice_metrics(test, test_calibrated),
    }

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "hazard_model_report.json").write_text(json.dumps(report, indent=2))
    _persist(booster, calibrator, model_version, out / "models")
    return report


def _slice_metrics(test: pd.DataFrame, y_prob: np.ndarray) -> dict[str, Any]:
    t = test.copy()
    t["_prob"] = y_prob
    slices: dict[str, Any] = {}
    for group_col, label in [
        ("method", "by_method"),
        ("merchant_category", "by_merchant_category"),
        ("regime_shift_bank", "by_regime_shift_bank"),
    ]:
        block: dict[str, Any] = {}
        for key, g in t.groupby(group_col, observed=True):
            y_true = g[LABEL_COLUMN].to_numpy()
            y_p = g["_prob"].to_numpy()
            if len(g) < MIN_SLICE_N or len(np.unique(y_true)) < 2:
                block[str(key)] = {"n": int(len(g)), "status": "insufficient_data"}
            else:
                block[str(key)] = metric_block(y_true, y_p)
        slices[label] = block
    return slices


def _persist(
    booster: lgb.Booster, calibrator: IsotonicRegression, model_version: str, out_dir: Path
) -> None:
    import joblib

    out_dir.mkdir(parents=True, exist_ok=True)
    joblib.dump(booster, out_dir / f"hazard_lgbm_{model_version}.joblib")
    joblib.dump(calibrator, out_dir / f"hazard_calibrator_{model_version}.joblib")


def load_hazard_model(
    model_version: str, models_dir: str = "artifacts/models"
) -> TrainedHazardModel:
    """Loads a `TrainedHazardModel` back from the joblib artifacts `_persist` wrote,
    named exactly `hazard_lgbm_{model_version}.joblib` /
    `hazard_calibrator_{model_version}.joblib`. Used by `agent/models.py::ModelBundle`
    for decision-time inference — training (`train_hazard_model`) never needs this.
    """
    import joblib

    d = Path(models_dir)
    booster = joblib.load(d / f"hazard_lgbm_{model_version}.joblib")
    calibrator = joblib.load(d / f"hazard_calibrator_{model_version}.joblib")
    return TrainedHazardModel(booster=booster, calibrator=calibrator, model_version=model_version)
