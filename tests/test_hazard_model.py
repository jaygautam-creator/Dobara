from __future__ import annotations

from pathlib import Path

from models.hazard import train_hazard_model
from sim.engine import run_simulation
from sim.params import load_params


def test_train_hazard_model_end_to_end(tmp_path: Path) -> None:
    params = load_params()
    db_path = tmp_path / "hazard.sqlite3"
    run_simulation(
        params, seed=42, db_path=str(db_path), n_customers=4000, n_cycles=8, n_merchants=20
    )

    out_dir = tmp_path / "artifacts"
    report = train_hazard_model(str(db_path), out_dir=str(out_dir))

    assert report["n_train"] > 0
    assert report["n_test"] > 0
    assert report["n_test_evaluations"] == 1

    for calib_key in ("calibrated", "uncalibrated"):
        block = report[calib_key]
        assert 0.0 <= block["brier_score"]["point"] <= 1.0
        assert block["roc_auc"]["point"] >= 0.5

    headline = report["headline_marginal_hazard"]
    assert "mean_hazard_by_failure_count" in headline
    assert "survival_curve" in headline
    # survival must be non-increasing as failure count rises
    survival = headline["survival_curve"]
    keys_sorted = sorted(int(k) for k in survival)
    values = [survival[str(k)] for k in keys_sorted]
    assert all(a >= b - 1e-9 for a, b in zip(values, values[1:], strict=False))
    assert values[0] == 1.0

    assert "by_method" in report["slices"]
    assert "by_regime_shift_bank" in report["slices"]

    assert (out_dir / "hazard_model_report.json").exists()
    model_files = list((out_dir / "models").glob("hazard_*.joblib"))
    assert len(model_files) == 2


def test_marginal_hazard_headline_shape() -> None:
    import numpy as np
    import pandas as pd

    from models.hazard import marginal_hazard_by_failure_count

    test = pd.DataFrame(
        {
            "failure_notifications_this_cycle": [0, 0, 1, 1, 2, 2],
        }
    )
    y_prob = np.array([0.05, 0.06, 0.15, 0.17, 0.30, 0.28])
    out = marginal_hazard_by_failure_count(test, y_prob)
    assert out["mean_hazard_by_failure_count"]["0"]["mean_hazard"] < 0.1
    assert out["mean_hazard_by_failure_count"]["2"]["mean_hazard"] > 0.2
    assert out["marginal_hazard_deltas"]["0_to_1"] > 0
    assert out["survival_curve"]["0"] == 1.0
    assert out["survival_curve"]["2"] < out["survival_curve"]["1"] < out["survival_curve"]["0"]
