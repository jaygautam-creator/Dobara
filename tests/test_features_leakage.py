"""Leakage test: no feature reads post-decision data. Method — mutate a later attempt's
outcome, recompute bank health + features, and assert every EARLIER row's features are
byte-identical to before the mutation. If any feature depended on future data, this would
change. See docs/02-ARCHITECTURE.md `features/` module contract.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, text

from features.recovery import LABEL_COLUMN, RECOVERY_FEATURE_COLUMNS, build_recovery_features
from models.bank_health import compute_bank_health_snapshots
from sim.engine import run_simulation
from sim.params import load_params


def _flip_a_middle_attempt_outcome(db_path: str) -> pd.Timestamp:
    engine = create_engine(f"sqlite:///{db_path}")
    with engine.begin() as conn:
        rows = conn.execute(
            text("SELECT id, outcome, scheduled_at FROM attempts ORDER BY scheduled_at, id")
        ).fetchall()
        mid = rows[len(rows) // 2]
        new_outcome = "success" if mid.outcome != "success" else "soft_decline"
        conn.execute(
            text("UPDATE attempts SET outcome = :o WHERE id = :id"),
            {"o": new_outcome, "id": mid.id},
        )
        conn.execute(text("DELETE FROM bank_health_snapshots"))
    return pd.Timestamp(mid.scheduled_at)


def test_earlier_rows_unaffected_by_later_outcome_mutation(tmp_path: Path) -> None:
    params = load_params()
    db_path = tmp_path / "leakage.sqlite3"
    run_simulation(params, seed=9, db_path=str(db_path), n_customers=300, n_cycles=6, n_merchants=8)

    compute_bank_health_snapshots(str(db_path))
    before = build_recovery_features(str(db_path)).set_index("attempt_id").sort_index()

    mutated_at = _flip_a_middle_attempt_outcome(str(db_path))
    compute_bank_health_snapshots(str(db_path))
    after = build_recovery_features(str(db_path)).set_index("attempt_id").sort_index()

    all_ids = before.index
    earlier_mask = _scheduled_before(str(db_path), all_ids, mutated_at)
    earlier_ids = all_ids[earlier_mask]

    compare_cols = [c for c in RECOVERY_FEATURE_COLUMNS if c in before.columns] + [LABEL_COLUMN]
    pd.testing.assert_frame_equal(
        before.loc[earlier_ids, compare_cols],
        after.loc[earlier_ids, compare_cols],
        check_like=False,
    )
    assert len(earlier_ids) > 0


def _scheduled_before(db_path: str, attempt_ids: pd.Index, cutoff: pd.Timestamp) -> pd.Series:
    engine = create_engine(f"sqlite:///{db_path}")
    df = pd.read_sql(
        "SELECT id AS attempt_id, scheduled_at FROM attempts", engine, parse_dates=["scheduled_at"]
    ).set_index("attempt_id")
    aligned = df.loc[attempt_ids, "scheduled_at"]
    return (aligned < cutoff).to_numpy()
