from __future__ import annotations

from pathlib import Path

from models.bank_health import compute_bank_health_snapshots
from models.recovery import train_recovery_model
from sim.engine import run_simulation
from sim.params import load_params


def test_train_recovery_model_end_to_end(tmp_path: Path) -> None:
    params = load_params()
    db_path = tmp_path / "recovery.sqlite3"
    run_simulation(
        params, seed=42, db_path=str(db_path), n_customers=2000, n_cycles=8, n_merchants=15
    )
    compute_bank_health_snapshots(str(db_path))

    out_dir = tmp_path / "artifacts"
    report = train_recovery_model(str(db_path), out_dir=str(out_dir))

    assert report["n_train"] > 0
    assert report["n_validate"] > 0
    assert report["n_test"] > 0
    assert report["n_test_evaluations"] == 1

    for model_key in ("lightgbm", "logistic_baseline"):
        for calib_key in ("calibrated", "uncalibrated"):
            block = report[model_key][calib_key]
            assert 0.0 <= block["brier_score"]["point"] <= 1.0
            assert 0.5 <= block["roc_auc"]["point"] <= 1.0  # sanity: better than a coin flip
            # every metric carries a CI (may be NaN only if the slice was too small — not
            # the case for the full test split)
            assert block["brier_score"]["ci_lo"] == block["brier_score"]["ci_lo"]  # not NaN

    assert isinstance(report["beats_baseline"], bool)
    assert "by_bank" in report["slices"]
    assert "by_method" in report["slices"]
    assert "by_attempt_index" in report["slices"]
    assert "by_regime_shift_bank" in report["slices"]

    assert (out_dir / "recovery_model_report.json").exists()
    model_files = list((out_dir / "models").glob("*.joblib"))
    assert len(model_files) == 4


def test_calibration_improves_or_matches_brier(tmp_path: Path) -> None:
    """Isotonic calibration should not make Brier meaningfully worse than the raw score."""
    params = load_params()
    db_path = tmp_path / "recovery2.sqlite3"
    run_simulation(
        params, seed=7, db_path=str(db_path), n_customers=2000, n_cycles=8, n_merchants=15
    )
    compute_bank_health_snapshots(str(db_path))
    report = train_recovery_model(str(db_path), out_dir=str(tmp_path / "artifacts2"))

    calibrated = report["lightgbm"]["calibrated"]["brier_score"]["point"]
    uncalibrated = report["lightgbm"]["uncalibrated"]["brier_score"]["point"]
    assert calibrated <= uncalibrated + 0.02  # small slack for sampling noise
