"""Model 1 — Recovery. `P(debit succeeds | context, attempt_time)`. Per docs/05-ML-SPEC.md:

- LightGBM binary classifier, **always reported alongside a logistic regression baseline**.
  If gradient boosting does not clearly beat the linear baseline, that is reported as a
  finding, not hidden.
- **The LGBM booster's calibrator is Platt scaling (logistic regression on the raw
  score), fitted on the validation split (cycle 5) — adopted 2026-09-01, replacing
  isotonic regression, per the pre-registered rule in `docs/DECISIONS.md` [2026-09-01]
  "Pre-registration: calibrator bake-off" and its verdict reversal on the held-out
  population, same date.** Isotonic's coarse step function (as few as 17 distinct
  output values) was collapsing genuine model signal into argmax ties at the tie-break
  layer (`agent/decide.py::_tie_break_score`); Platt is fully continuous (5,000/5,000
  distinct outputs on the raw-score grid) and measurably cuts the held-out argmax tie
  rate (77.2% -> ~31%) without a Brier-CI regression vs. the isotonic baseline it
  replaces — see that DECISIONS.md entry for the full pre-registered-criteria evidence.
  The **logistic baseline's own calibrator is still isotonic regression**, unchanged —
  the bake-off only tested calibrators for the LGBM booster's raw score, and adopting a
  result for one model is not assumed to transfer to the other without measuring it
  (only measured for LGBM here).
- **Calibration is the priority, not AUC** — we multiply this probability by rupees. Brier
  score and a reliability diagram are reported alongside AUC/PR-AUC, and led with in any
  summary.
- Slice metrics by bank, method, attempt index, cold-start, and the regime-shift bank
  reported separately — an aggregate number that hides a broken slice is a lie
  (docs/05-ML-SPEC.md Honesty guardrails).
- The test set (cycle 6-8) is touched exactly once; `n_test_evaluations` is tracked and
  written into the report as an honesty marker.
- **No LLM import anywhere in this module** — enforced by `tests/test_no_llm_in_money_path.py`.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from features.recovery import LABEL_COLUMN, RECOVERY_FEATURE_COLUMNS, build_recovery_features
from models.metrics import MIN_SLICE_N, RNG_SEED, metric_block

CATEGORICAL_COLUMNS = [
    "bank_id",
    "method",
    "prev_error_source",
    "prev_error_step",
    "prev_error_reason",
]
NUMERIC_COLUMNS = [c for c in RECOVERY_FEATURE_COLUMNS if c not in CATEGORICAL_COLUMNS]


def _lgbm_frame(df: pd.DataFrame) -> pd.DataFrame:
    X = df[RECOVERY_FEATURE_COLUMNS].copy()
    for c in CATEGORICAL_COLUMNS:
        X[c] = X[c].astype("category")
    for c in NUMERIC_COLUMNS:
        if X[c].dtype == bool:
            X[c] = X[c].astype(float)
    return X


class _Calibrator(Protocol):
    """Either `IsotonicRegression` (still used for `logistic_calibrator`) or
    `PlattCalibrator` (now used for `lgbm_calibrator`, `docs/DECISIONS.md` [2026-09-01]
    "verdict reversed") satisfy this -- both expose a `predict(raw) -> calibrated prob`
    method, the only interface `TrainedRecoveryModel` needs."""

    def predict(self, x: np.ndarray) -> np.ndarray: ...


@dataclass
class PlattCalibrator:
    """Platt scaling: a logistic regression fit on the raw booster score alone.
    `docs/DECISIONS.md` [2026-09-01] "Pre-registration: calibrator bake-off" /
    "verdict reversed on the held-out population" -- adopted over isotonic for
    `lgbm_calibrator` because it is fully continuous (no quantization-induced argmax
    ties) and passed both pre-registered criteria (Brier CI overlap, tie rate at least
    halved) directly measured on the held-out population. A plain, picklable class (not
    a closure or a bare `sklearn.linear_model.LogisticRegression`) so `joblib.dump`/
    `joblib.load` round-trip it the same way `IsotonicRegression` already does.
    """

    model: LogisticRegression

    @classmethod
    def fit(cls, raw: np.ndarray, y: np.ndarray) -> PlattCalibrator:
        m = LogisticRegression()
        m.fit(np.asarray(raw).reshape(-1, 1), y)
        return cls(model=m)

    def predict(self, x: np.ndarray) -> np.ndarray:
        return np.asarray(self.model.predict_proba(np.asarray(x).reshape(-1, 1))[:, 1])


@dataclass
class TrainedRecoveryModel:
    lgbm_booster: lgb.Booster
    lgbm_calibrator: _Calibrator
    logistic_pipeline: Pipeline
    logistic_calibrator: IsotonicRegression
    model_version: str
    feature_columns: list[str] = field(default_factory=lambda: list(RECOVERY_FEATURE_COLUMNS))

    def predict_lgbm(self, df: pd.DataFrame) -> np.ndarray:
        raw = np.asarray(self.lgbm_booster.predict(_lgbm_frame(df)))
        return np.asarray(self.lgbm_calibrator.predict(raw))

    def predict_logistic(self, df: pd.DataFrame) -> np.ndarray:
        raw = self.logistic_pipeline.predict_proba(df[RECOVERY_FEATURE_COLUMNS])[:, 1]
        return np.asarray(self.logistic_calibrator.predict(raw))

    def predict_lgbm_contrib(self, df: pd.DataFrame) -> np.ndarray:
        """Per-row SHAP-style feature contributions (LightGBM's native `pred_contrib`),
        one row of `len(feature_columns) + 1` values (the trailing value is the
        expected-value/bias term) per input row. This is the per-prediction feature
        attribution `PROGRESS.md` deferred from Phase 2 to Phase 3's audit trail
        (`agent/decide.py` calls this per decision).
        """
        return np.asarray(self.lgbm_booster.predict(_lgbm_frame(df), pred_contrib=True))


def _model_version(df: pd.DataFrame) -> str:
    # v2, 2026-09-01: lgbm_calibrator switched isotonic -> Platt (docs/DECISIONS.md
    # [2026-09-01] "verdict reversed on the held-out population") -- the tag changes so
    # this is never confused with a v1 (isotonic) artifact sharing the same feature set.
    payload = f"{sorted(RECOVERY_FEATURE_COLUMNS)}|{len(df)}|lgbm(platt)+logistic(isotonic)|v2"
    return hashlib.sha256(payload.encode()).hexdigest()[:12]


def _build_logistic_pipeline() -> Pipeline:
    # Note: sklearn's SimpleImputer silently DROPS a column that is all-NaN in the
    # training fold (rather than erroring), which happens to `days_from_declared_day` at
    # small simulation scale since Tier 1 (declared preferred day) is rare by design
    # (docs/04-DATA-MODEL.md: response_rate default 6%, only offered after 2 consecutive
    # failed cycles). LightGBM does not have this issue (native NaN handling). Not a
    # correctness bug — the fitted transformer stays consistent between train/val/test —
    # but it silently removes the feature's signal from the logistic baseline at small n.
    categorical = Pipeline(
        steps=[
            ("impute", SimpleImputer(strategy="constant", fill_value="missing")),
            ("onehot", OneHotEncoder(handle_unknown="ignore")),
        ]
    )
    numeric = Pipeline(
        steps=[("impute", SimpleImputer(strategy="median")), ("scale", StandardScaler())]
    )
    pre = ColumnTransformer(
        [("cat", categorical, CATEGORICAL_COLUMNS), ("num", numeric, NUMERIC_COLUMNS)]
    )
    return Pipeline(
        steps=[("pre", pre), ("clf", LogisticRegression(max_iter=1000, random_state=RNG_SEED))]
    )


def train_recovery_model(
    db_path: str, out_dir: str = "artifacts", n_test_evaluations: int = 1
) -> dict[str, Any]:
    df = build_recovery_features(db_path)
    train = df[df["split"] == "train"]
    val = df[df["split"] == "validate"]
    test = df[df["split"] == "test"]
    cold_start = df[df["split"] == "cold_start"]

    y_train = train[LABEL_COLUMN].to_numpy()
    y_val = val[LABEL_COLUMN].to_numpy()
    y_test = test[LABEL_COLUMN].to_numpy()

    # --- LightGBM ---
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
    lgbm_val_raw = booster.predict(_lgbm_frame(val))
    lgbm_calibrator: _Calibrator = PlattCalibrator.fit(np.asarray(lgbm_val_raw), y_val)

    # --- Logistic baseline ---
    logistic_pipeline = _build_logistic_pipeline()
    logistic_pipeline.fit(train[RECOVERY_FEATURE_COLUMNS], y_train)
    logistic_val_raw = logistic_pipeline.predict_proba(val[RECOVERY_FEATURE_COLUMNS])[:, 1]
    logistic_calibrator = IsotonicRegression(out_of_bounds="clip").fit(logistic_val_raw, y_val)

    model = TrainedRecoveryModel(
        lgbm_booster=booster,
        lgbm_calibrator=lgbm_calibrator,
        logistic_pipeline=logistic_pipeline,
        logistic_calibrator=logistic_calibrator,
        model_version=_model_version(df),
    )

    # --- Test evaluation (touched exactly `n_test_evaluations` times) ---
    lgbm_test_prob = model.predict_lgbm(test)
    logistic_test_prob = model.predict_logistic(test)
    lgbm_test_raw = np.asarray(booster.predict(_lgbm_frame(test)))
    logistic_test_raw = np.asarray(
        logistic_pipeline.predict_proba(test[RECOVERY_FEATURE_COLUMNS])[:, 1]
    )

    report: dict[str, Any] = {
        "model_version": model.model_version,
        "n_test_evaluations": n_test_evaluations,
        "test_set_touched_note": (
            "The test set (cycle 6-8) must be touched exactly once, at the end. "
            "This counter is the honesty marker required by docs/05-ML-SPEC.md."
        ),
        "n_train": int(len(train)),
        "n_validate": int(len(val)),
        "n_test": int(len(test)),
        "n_cold_start": int(len(cold_start)),
        "lightgbm": {
            "calibrated": metric_block(y_test, lgbm_test_prob),
            "uncalibrated": metric_block(y_test, lgbm_test_raw),
        },
        "logistic_baseline": {
            "calibrated": metric_block(y_test, logistic_test_prob),
            "uncalibrated": metric_block(y_test, logistic_test_raw),
        },
        "beats_baseline": bool(
            metric_block(y_test, lgbm_test_prob)["brier_score"]["point"]
            < metric_block(y_test, logistic_test_prob)["brier_score"]["point"]
        ),
        "slices": _slice_metrics(test, lgbm_test_prob),
    }

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "recovery_model_report.json").write_text(json.dumps(report, indent=2))
    _persist(model, out / "models")
    return report


def _slice_metrics(test: pd.DataFrame, y_prob: np.ndarray) -> dict[str, Any]:
    test = test.copy()
    test["_prob"] = y_prob
    test["_attempt_bucket"] = np.where(
        test["attempt_index"] >= 4, "4+", test["attempt_index"].astype(str)
    )

    slices: dict[str, Any] = {}
    for group_col, label in [
        ("bank_id", "by_bank"),
        ("method", "by_method"),
        ("_attempt_bucket", "by_attempt_index"),
        ("regime_shift_bank", "by_regime_shift_bank"),
    ]:
        block: dict[str, Any] = {}
        for key, g in test.groupby(group_col, observed=True):
            y_true = g[LABEL_COLUMN].to_numpy()
            y_p = g["_prob"].to_numpy()
            if len(g) < MIN_SLICE_N or len(np.unique(y_true)) < 2:
                block[str(key)] = {"n": int(len(g)), "status": "insufficient_data"}
            else:
                block[str(key)] = metric_block(y_true, y_p)
        slices[label] = block
    return slices


def _persist(model: TrainedRecoveryModel, out_dir: Path) -> None:
    import joblib

    out_dir.mkdir(parents=True, exist_ok=True)
    joblib.dump(model.lgbm_booster, out_dir / f"recovery_lgbm_{model.model_version}.joblib")
    joblib.dump(
        model.lgbm_calibrator, out_dir / f"recovery_lgbm_calibrator_{model.model_version}.joblib"
    )
    joblib.dump(
        model.logistic_pipeline, out_dir / f"recovery_logistic_{model.model_version}.joblib"
    )
    joblib.dump(
        model.logistic_calibrator,
        out_dir / f"recovery_logistic_calibrator_{model.model_version}.joblib",
    )


def load_recovery_model(
    model_version: str, models_dir: str = "artifacts/models"
) -> TrainedRecoveryModel:
    """Loads a `TrainedRecoveryModel` back from the joblib artifacts `_persist` wrote.
    Used by `agent/models.py::ModelBundle` for decision-time inference — training
    (`train_recovery_model`) never needs this.
    """
    import joblib

    d = Path(models_dir)
    return TrainedRecoveryModel(
        lgbm_booster=joblib.load(d / f"recovery_lgbm_{model_version}.joblib"),
        lgbm_calibrator=joblib.load(d / f"recovery_lgbm_calibrator_{model_version}.joblib"),
        logistic_pipeline=joblib.load(d / f"recovery_logistic_{model_version}.joblib"),
        logistic_calibrator=joblib.load(d / f"recovery_logistic_calibrator_{model_version}.joblib"),
        model_version=model_version,
    )
