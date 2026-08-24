"""The leakage boundary for Model 1 (recovery). Every feature is computed from
information available strictly before its attempt's `scheduled_at`. See
docs/02-ARCHITECTURE.md (`features/` module contract) and docs/05-ML-SPEC.md.

**No import of `sim.latent` anywhere in this package** — enforced by
`tests/test_latent_isolation.py`. **No feature may encode individual balance or income**
(rule `DPDP-MINIMISE`) — enforced by `assert_no_banned_features` below and
`tests/test_features_banned.py`.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

import pandas as pd
from sqlalchemy import create_engine

from models.bank_health import load_snapshots
from sim.splits import split_for_cycle

BANNED_FEATURE_SUBSTRINGS = (
    "balance",
    "income",
    "cashflow",
    "cash_flow",
    "spend",
    "salary",
)

RECOVERY_FEATURE_COLUMNS = [
    # Bank
    "bank_id",
    "bank_health_ewma",
    "bank_health_changepoint",
    "bank_dow_profile",
    "is_bank_holiday",
    # Method
    "method",
    "method_x_bank_success_rate",
    # History (Tier 2)
    "attempt_index",
    "hours_since_last_attempt",
    "prior_failures_this_cycle",
    "consecutive_failed_cycles",
    "mandate_success_rate_to_date",
    "mandate_age_cycles",
    # Timing (Tier 3)
    "day_of_month",
    "is_month_start_window",
    "is_mid_month_window",
    "day_of_week",
    "days_until_cycle_end",
    # Amount
    "amount",
    "amount_vs_afa_threshold",
    "amount_vs_mandate_typical",
    # Cause
    "prev_error_source",
    "prev_error_step",
    "prev_error_reason",
    # Declared (Tier 1)
    "has_declared_preferred_day",
    "days_from_declared_day",
]

LABEL_COLUMN = "label_success"
CYCLE_LENGTH_DAYS = 30  # matches sim.engine's fixed 30-day cycle spacing
AFA_THRESHOLD_INR = 15000.0


def assert_no_banned_features(columns: list[str]) -> None:
    """Name-based guard, not a semantic one — it catches naming, not meaning. It cannot
    detect a differently-named feature that is functionally a balance/income proxy. The
    real guarantee is the import boundary (`features/` has no import path to
    `sim.latent`, enforced by `tests/test_latent_isolation.py`) plus review; this function
    is a stated commitment and a backstop, not a proof. See README "What Dobara
    deliberately does not do".
    """
    for c in columns:
        low = c.lower()
        for bad in BANNED_FEATURE_SUBSTRINGS:
            if bad in low:
                raise ValueError(
                    f"banned feature name: '{c}' (contains '{bad}') — DPDP-MINIMISE, "
                    "docs/01-REGULATORY.md. No feature may encode individual balance "
                    "or income."
                )


assert_no_banned_features(RECOVERY_FEATURE_COLUMNS)


@dataclass
class _MandateHistory:
    n_attempts: int = 0
    n_successes: int = 0
    last_attempt_at: pd.Timestamp | None = None
    current_cycle_id: int | None = None
    prior_failures_this_cycle: int = 0
    cycle_had_success: bool = False
    consecutive_failed_cycles: int = 0
    prev_error_source: str | None = None
    prev_error_step: str | None = None
    prev_error_reason: str | None = None


def _load_raw(db_path: str) -> pd.DataFrame:
    engine = create_engine(f"sqlite:///{db_path}")
    query = """
    SELECT
        a.id AS attempt_id,
        a.cycle_id,
        a.attempt_index,
        a.scheduled_at,
        a.outcome,
        a.error_source,
        a.error_step,
        a.error_reason,
        m.id AS mandate_id,
        m.amount,
        m.method,
        cu.bank_id,
        cu.preferred_debit_day,
        cy.cycle_index,
        cy.due_date,
        m.is_cold_start,
        m.regime_shift_bank
    FROM attempts a
    JOIN cycles cy ON a.cycle_id = cy.id
    JOIN mandates m ON cy.mandate_id = m.id
    JOIN customers cu ON m.customer_id = cu.id
    ORDER BY a.scheduled_at, a.id
    """
    return pd.read_sql(query, engine, parse_dates=["scheduled_at", "due_date"])


def _on_cycle_transition(h: _MandateHistory, new_cycle_id: int) -> None:
    """Called when an attempt belongs to a different cycle than the mandate's last-seen
    one — i.e. the previous cycle is now fully in the past. Rolls its outcome into
    `consecutive_failed_cycles` before resetting per-cycle counters.
    """
    if h.current_cycle_id is not None:
        h.consecutive_failed_cycles = 0 if h.cycle_had_success else h.consecutive_failed_cycles + 1
    h.current_cycle_id = new_cycle_id
    h.prior_failures_this_cycle = 0
    h.cycle_had_success = False


def build_recovery_features(db_path: str) -> pd.DataFrame:
    """One row per historical `Attempt`. Features computed strictly from data available
    before that attempt's `scheduled_at`: prior attempts/cycles on the *same* mandate,
    and the most recent bank-health snapshot strictly before `scheduled_at` (an as-of
    join, never the snapshot produced by the current attempt itself).
    """
    raw = _load_raw(db_path)
    snapshots = load_snapshots(db_path)

    rows: list[dict[str, object]] = []
    histories: dict[int, _MandateHistory] = defaultdict(_MandateHistory)

    for row in raw.itertuples(index=False):
        h = histories[row.mandate_id]
        if h.current_cycle_id != row.cycle_id:
            _on_cycle_transition(h, row.cycle_id)

        hours_since_last = (
            (row.scheduled_at - h.last_attempt_at).total_seconds() / 3600
            if h.last_attempt_at is not None
            else float("nan")
        )

        bank_snap = snapshots[
            (snapshots["bank_id"] == row.bank_id)
            & (snapshots["method"] == row.method)
            & (snapshots["as_of"] < row.scheduled_at)
        ].tail(1)
        bank_health_ewma = (
            float(bank_snap["ewma_success"].iloc[0]) if len(bank_snap) else float("nan")
        )
        bank_health_changepoint = (
            bool(bank_snap["changepoint_flag"].iloc[0]) if len(bank_snap) else False
        )

        has_declared = row.preferred_debit_day is not None
        days_from_declared = (
            abs(row.due_date.day - row.preferred_debit_day) if has_declared else float("nan")
        )

        days_until_cycle_end = CYCLE_LENGTH_DAYS - (row.scheduled_at - row.due_date).days

        rows.append(
            {
                "attempt_id": row.attempt_id,
                "mandate_id": row.mandate_id,
                "bank_id": row.bank_id,
                "bank_health_ewma": bank_health_ewma,
                "bank_health_changepoint": bank_health_changepoint,
                "bank_dow_profile": row.scheduled_at.weekday(),
                "is_bank_holiday": row.scheduled_at.weekday() == 6,  # Sunday, a simplification
                "method": row.method,
                "method_x_bank_success_rate": (
                    h.n_successes / h.n_attempts if h.n_attempts else float("nan")
                ),
                "attempt_index": row.attempt_index,
                "hours_since_last_attempt": hours_since_last,
                "prior_failures_this_cycle": h.prior_failures_this_cycle,
                "consecutive_failed_cycles": h.consecutive_failed_cycles,
                "mandate_success_rate_to_date": (
                    h.n_successes / h.n_attempts if h.n_attempts else float("nan")
                ),
                "mandate_age_cycles": row.cycle_index - 1,
                "day_of_month": row.scheduled_at.day,
                "is_month_start_window": row.scheduled_at.day <= 5,
                "is_mid_month_window": 10 <= row.scheduled_at.day <= 20,
                "day_of_week": row.scheduled_at.weekday(),
                "days_until_cycle_end": days_until_cycle_end,
                "amount": row.amount,
                "amount_vs_afa_threshold": row.amount / AFA_THRESHOLD_INR,
                "amount_vs_mandate_typical": 1.0,  # amount is fixed per mandate in sim v1
                "prev_error_source": h.prev_error_source,
                "prev_error_step": h.prev_error_step,
                "prev_error_reason": h.prev_error_reason,
                "has_declared_preferred_day": has_declared,
                "days_from_declared_day": days_from_declared,
                LABEL_COLUMN: row.outcome == "success",
                # split-assignment metadata — NOT model features, consumed by
                # sim/splits.py + models/recovery.py to build train/val/test/cold_start
                "cycle_index": row.cycle_index,
                "is_cold_start": bool(row.is_cold_start),
                "regime_shift_bank": bool(row.regime_shift_bank),
            }
        )

        # update history AFTER emitting this row's features — never before
        success = row.outcome == "success"
        h.n_attempts += 1
        h.n_successes += int(success)
        h.last_attempt_at = row.scheduled_at
        if success:
            h.cycle_had_success = True
        else:
            h.prior_failures_this_cycle += 1
        h.prev_error_source = None if success else row.error_source
        h.prev_error_step = None if success else row.error_step
        h.prev_error_reason = None if success else row.error_reason

    df = pd.DataFrame(rows)
    assert_no_banned_features(list(df.columns))
    df["split"] = [
        split_for_cycle(int(ci), bool(cs))
        for ci, cs in zip(df["cycle_index"], df["is_cold_start"], strict=True)
    ]
    return df
