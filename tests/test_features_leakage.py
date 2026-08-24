"""Leakage test: no feature reads post-decision data. Two mutation styles, because they
catch different bug classes:

1. Mutate a later attempt's OUTCOME — catches a feature reading a future row's value.
2. INSERT a brand new, later attempt — catches a feature reading the mere EXISTENCE of a
   future row (e.g. a hypothetical `days_until_next_attempt`). No current feature does
   this, but the list grows in Phase 2 and this failure mode would not be caught by (1)
   alone.

Both assert every EARLIER row's features are byte-identical before vs after. See
docs/02-ARCHITECTURE.md `features/` module contract.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from features.recovery import LABEL_COLUMN, RECOVERY_FEATURE_COLUMNS, build_recovery_features
from models.bank_health import compute_bank_health_snapshots
from sim.engine import run_simulation
from sim.params import load_params
from sim.schema import Attempt


def _compare_cols(columns: list[str]) -> list[str]:
    """The full feature list plus the label — asserted complete so a column silently
    renamed in features/recovery.py but not RECOVERY_FEATURE_COLUMNS can't shrink this
    list and have the test keep passing while checking almost nothing. Same failure mode
    as a benchmark check that only prints (docs/DECISIONS.md [2026-08-25], calibration
    gate entry).
    """
    cols = [c for c in RECOVERY_FEATURE_COLUMNS if c in columns] + [LABEL_COLUMN]
    assert len(cols) == len(RECOVERY_FEATURE_COLUMNS) + 1, (
        f"expected all {len(RECOVERY_FEATURE_COLUMNS)} declared feature columns + label "
        f"to be present in the built DataFrame; got {len(cols)}. A column was likely "
        "renamed in features/recovery.py without updating RECOVERY_FEATURE_COLUMNS, which "
        "would silently narrow what this leakage test actually checks."
    )
    return cols


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


def _insert_a_new_later_attempt(db_path: str) -> pd.Timestamp:
    """Inserts a brand new attempt, chronologically after everything else, into the same
    cycle as the current globally-last attempt. Returns that new attempt's scheduled_at —
    every pre-existing attempt is earlier than it by construction.

    Goes through the SQLAlchemy ORM (like `sim/engine.py` does), not a raw-SQL string
    literal for `scheduled_at`: a raw string without SQLAlchemy's microsecond suffix reads
    back with a different textual format than ORM-written rows, and pandas' `read_sql`
    format-inference silently turns the mismatched rows into `NaT` instead of raising —
    a real bug hit while writing this test.
    """
    engine = create_engine(f"sqlite:///{db_path}")
    with Session(engine) as session:
        last = (
            session.query(Attempt).order_by(Attempt.scheduled_at.desc(), Attempt.id.desc()).first()
        )
        assert last is not None
        new_scheduled_at = last.scheduled_at + pd.Timedelta(hours=24)
        session.add(
            Attempt(
                cycle_id=last.cycle_id,
                attempt_index=last.attempt_index + 1,
                scheduled_at=new_scheduled_at,
                executed_at=new_scheduled_at,
                outcome="success",
                error_source=None,
                error_step=None,
                error_reason=None,
                gateway_ref="rzp_test_leak_insert",
                had_valid_pdn=True,
            )
        )
        session.commit()
    with create_engine(f"sqlite:///{db_path}").begin() as conn:
        conn.execute(text("DELETE FROM bank_health_snapshots"))
    return pd.Timestamp(new_scheduled_at)


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

    compare_cols = _compare_cols(list(before.columns))
    pd.testing.assert_frame_equal(
        before.loc[earlier_ids, compare_cols],
        after.loc[earlier_ids, compare_cols],
        check_like=False,
    )
    assert len(earlier_ids) > 0


def test_earlier_rows_unaffected_by_a_new_later_attempt(tmp_path: Path) -> None:
    params = load_params()
    db_path = tmp_path / "leakage_insert.sqlite3"
    run_simulation(
        params, seed=13, db_path=str(db_path), n_customers=300, n_cycles=6, n_merchants=8
    )

    compute_bank_health_snapshots(str(db_path))
    before = build_recovery_features(str(db_path)).set_index("attempt_id").sort_index()

    _insert_a_new_later_attempt(str(db_path))
    compute_bank_health_snapshots(str(db_path))
    after = build_recovery_features(str(db_path)).set_index("attempt_id").sort_index()

    # every original attempt_id is, by construction, earlier than the newly inserted one
    original_ids = before.index

    compare_cols = _compare_cols(list(before.columns))
    pd.testing.assert_frame_equal(
        before.loc[original_ids, compare_cols],
        after.loc[original_ids, compare_cols],
        check_like=False,
    )
    assert len(after) == len(before) + 1


def _scheduled_before(db_path: str, attempt_ids: pd.Index, cutoff: pd.Timestamp) -> pd.Series:
    engine = create_engine(f"sqlite:///{db_path}")
    df = pd.read_sql(
        "SELECT id AS attempt_id, scheduled_at FROM attempts", engine, parse_dates=["scheduled_at"]
    ).set_index("attempt_id")
    aligned = df.loc[attempt_ids, "scheduled_at"]
    return (aligned < cutoff).to_numpy()
