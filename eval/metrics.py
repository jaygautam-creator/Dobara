"""Generic bootstrap percentile CI for the eval harness's arm-level and paired-difference
metrics (mean net LTV per mandate, mean attempts per mandate, paired `dobara -
razorpay_default` differences, ...).

`models/metrics.py::bootstrap_ci` is Models 1/2's classification-metric bootstrap
(`roc_auc_score`/`brier_score_loss`/... over `(y_true, y_prob)` row pairs) — its
`len(np.unique(y_true)) < 2` guard exists so a slice with only one observed class isn't
silently reported with a fabricated CI, but that guard doesn't generalize to the
arm-level scalar metrics here (mean net LTV per mandate is not a `(y_true, y_prob)`
classification metric). `bootstrap_mean_ci` below is the same point-estimate-plus-
percentile-bootstrap shape, reusing `models.metrics`'s `RNG_SEED`/`N_BOOTSTRAP` constants
for consistency with the rest of the project's CI reporting, but built for an arbitrary
array of per-unit scalar values (per-mandate or per-seed).
"""

from __future__ import annotations

import numpy as np

from models.metrics import N_BOOTSTRAP, RNG_SEED


def bootstrap_mean_ci(values: np.ndarray, n: int = N_BOOTSTRAP) -> tuple[float, float, float]:
    """Point mean + (2.5th, 97.5th) percentile bootstrap CI over `values`. Returns
    `(point, nan, nan)` when there are too few values to resample meaningfully (mirrors
    `models.metrics.bootstrap_ci`'s `MIN_SLICE_N`-equivalent honesty guard, but sized for
    this harness's typical unit count — a seed-level metric with fewer than 2 seeds, or
    an empty mandate slice, cannot support a CI)."""
    values = np.asarray(values, dtype=float)
    point = float(values.mean()) if len(values) else float("nan")
    if len(values) < 2:
        return point, float("nan"), float("nan")
    rng = np.random.default_rng(RNG_SEED)
    draws = np.empty(n)
    for i in range(n):
        idx = rng.integers(0, len(values), len(values))
        draws[i] = values[idx].mean()
    lo, hi = np.percentile(draws, [2.5, 97.5])
    return point, float(lo), float(hi)
