"""Shared evaluation utilities for Models 1 and 2 (`models/recovery.py`,
`models/hazard.py`): bootstrap confidence intervals and the calibration-first metric
block. Every reported number carries a CI — CLAUDE.md non-negotiable: no bare point
estimates anywhere.
"""

from __future__ import annotations

from typing import Any

import numpy as np
from sklearn.calibration import calibration_curve
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score

MIN_SLICE_N = 30  # below this, a slice metric is reported as insufficient rather than guessed
N_BOOTSTRAP = 200
RNG_SEED = 42


def bootstrap_ci(
    y_true: np.ndarray, y_prob: np.ndarray, metric_fn: Any, n: int = N_BOOTSTRAP
) -> tuple[float, float, float]:
    """Point estimate + (2.5th, 97.5th) percentile bootstrap CI."""
    point = float(metric_fn(y_true, y_prob))
    rng = np.random.default_rng(RNG_SEED)
    n_rows = len(y_true)
    if n_rows < MIN_SLICE_N or len(np.unique(y_true)) < 2:
        return point, float("nan"), float("nan")
    draws = []
    for _ in range(n):
        idx = rng.integers(0, n_rows, n_rows)
        yt, yp = y_true[idx], y_prob[idx]
        if len(np.unique(yt)) < 2:
            continue
        draws.append(metric_fn(yt, yp))
    if not draws:
        return point, float("nan"), float("nan")
    lo, hi = np.percentile(draws, [2.5, 97.5])
    return point, float(lo), float(hi)


def metric_block(y_true: np.ndarray, y_prob: np.ndarray) -> dict[str, Any]:
    """Calibration-first metric block: Brier + reliability diagram before AUC/PR-AUC,
    per docs/05-ML-SPEC.md ("calibration is the priority, not AUC").
    """
    auc = bootstrap_ci(y_true, y_prob, roc_auc_score)
    pr_auc = bootstrap_ci(y_true, y_prob, average_precision_score)
    brier = bootstrap_ci(y_true, y_prob, brier_score_loss)
    n_bins = min(10, max(2, len(np.unique(y_prob)) // 5)) if len(y_true) >= MIN_SLICE_N else 2
    try:
        prob_true, prob_pred = calibration_curve(y_true, y_prob, n_bins=n_bins, strategy="quantile")
        reliability = {"prob_true": prob_true.tolist(), "prob_pred": prob_pred.tolist()}
    except ValueError:
        reliability = {"prob_true": [], "prob_pred": []}
    return {
        "n": int(len(y_true)),
        "brier_score": {"point": brier[0], "ci_lo": brier[1], "ci_hi": brier[2]},
        "reliability_diagram": reliability,
        "roc_auc": {"point": auc[0], "ci_lo": auc[1], "ci_hi": auc[2]},
        "pr_auc": {"point": pr_auc[0], "ci_lo": pr_auc[1], "ci_hi": pr_auc[2]},
    }
