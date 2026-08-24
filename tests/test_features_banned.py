from __future__ import annotations

import pytest

from features.recovery import (
    RECOVERY_FEATURE_COLUMNS,
    assert_no_banned_features,
    build_recovery_features,
)
from models.bank_health import compute_bank_health_snapshots
from sim.engine import run_simulation
from sim.params import load_params


def test_declared_feature_list_has_no_banned_names() -> None:
    assert_no_banned_features(RECOVERY_FEATURE_COLUMNS)  # must not raise


@pytest.mark.parametrize(
    "banned_name", ["customer_balance", "monthly_income", "cash_flow_proxy", "salary_amount"]
)
def test_banned_name_is_rejected(banned_name: str) -> None:
    with pytest.raises(ValueError, match="DPDP-MINIMISE"):
        assert_no_banned_features([banned_name])


def test_built_feature_frame_has_no_banned_columns(tmp_path) -> None:
    params = load_params()
    db_path = tmp_path / "banned.sqlite3"
    run_simulation(params, seed=5, db_path=str(db_path), n_customers=150, n_cycles=4, n_merchants=5)
    compute_bank_health_snapshots(str(db_path))
    df = build_recovery_features(str(db_path))
    assert_no_banned_features(list(df.columns))  # must not raise
