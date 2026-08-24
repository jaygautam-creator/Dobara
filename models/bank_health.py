"""Model 3 — Bank Health. EWMA of debit success per (bank x method) with an adaptive
decay rate (decay accelerates when recent variance rises), plus a rolling change-point
flag. Not learned end-to-end — a transparent statistical estimator, deliberately, per
docs/05-ML-SPEC.md, echoing Razorpay's published dynamic module (Bygari et al., IEEE Big
Data 2021).

Writes one `BankHealthSnapshot` row per (bank, method) after each attempt, so
`features/build.py` can as-of join against a snapshot strictly before the decision
timestamp — never the snapshot that includes the current attempt's own outcome.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field

import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from sim.schema import Attempt, BankHealthSnapshot, Customer, Cycle, Mandate

MIN_DECAY = 0.05
MAX_DECAY = 0.35
VARIANCE_WINDOW = 10
CHANGEPOINT_WINDOW = 8
CHANGEPOINT_THRESHOLD = 0.20  # absolute drop in recent-vs-prior success rate


@dataclass
class _SeriesState:
    ewma: float = 0.9  # neutral prior: most attempts succeed
    recent_outcomes: deque[int] = field(default_factory=lambda: deque(maxlen=VARIANCE_WINDOW))
    changepoint_window: deque[int] = field(
        default_factory=lambda: deque(maxlen=CHANGEPOINT_WINDOW * 2)
    )
    sample_n: int = 0


def adaptive_decay_rate(recent_outcomes: deque[int]) -> float:
    """Decay accelerates (higher rate = more weight on new data) when recent variance
    rises, so a degrading bank is detected quickly while a stable one is not over-reacted
    to.
    """
    if len(recent_outcomes) < 3:
        return MIN_DECAY
    p = sum(recent_outcomes) / len(recent_outcomes)
    variance = p * (1 - p)
    # variance in [0, 0.25]; map linearly onto [MIN_DECAY, MAX_DECAY]
    frac = min(variance / 0.25, 1.0)
    return MIN_DECAY + frac * (MAX_DECAY - MIN_DECAY)


def detect_changepoint(changepoint_window: deque[int]) -> bool:
    """Simple rolling-window test: split the window in half, flag if the recent half's
    success rate has dropped materially versus the earlier half.
    """
    if len(changepoint_window) < CHANGEPOINT_WINDOW * 2:
        return False
    values = list(changepoint_window)
    older = values[:CHANGEPOINT_WINDOW]
    recent = values[CHANGEPOINT_WINDOW:]
    return (sum(older) / len(older)) - (sum(recent) / len(recent)) > CHANGEPOINT_THRESHOLD


def update_ewma(state: _SeriesState, success: bool) -> _SeriesState:
    decay = adaptive_decay_rate(state.recent_outcomes)
    state.ewma = decay * float(success) + (1 - decay) * state.ewma
    state.recent_outcomes.append(int(success))
    state.changepoint_window.append(int(success))
    state.sample_n += 1
    return state


def compute_bank_health_snapshots(db_path: str) -> int:
    """Single pass, ordered by scheduled_at, over all attempts. Writes a
    `BankHealthSnapshot` after each attempt for that attempt's (bank, method). Returns the
    number of snapshots written.
    """
    engine = create_engine(f"sqlite:///{db_path}")
    with Session(engine) as session:
        rows = (
            session.query(
                Attempt.scheduled_at,
                Attempt.outcome,
                Mandate.method,
                Customer.bank_id,
            )
            .join(Cycle, Attempt.cycle_id == Cycle.id)
            .join(Mandate, Cycle.mandate_id == Mandate.id)
            .join(Customer, Mandate.customer_id == Customer.id)
            .order_by(Attempt.scheduled_at)
            .all()
        )

        states: dict[tuple[str, str], _SeriesState] = {}
        written = 0
        for scheduled_at, outcome, method, bank_id in rows:
            key = (bank_id, method)
            state = states.setdefault(key, _SeriesState())
            success = outcome == "success"
            update_ewma(state, success)
            snapshot = BankHealthSnapshot(
                bank_id=bank_id,
                method=method,
                as_of=scheduled_at,
                ewma_success=state.ewma,
                decay_rate=adaptive_decay_rate(state.recent_outcomes),
                changepoint_flag=detect_changepoint(state.changepoint_window),
                sample_n=state.sample_n,
            )
            session.add(snapshot)
            written += 1
        session.commit()
    return written


def load_snapshots(db_path: str) -> pd.DataFrame:
    engine = create_engine(f"sqlite:///{db_path}")
    return pd.read_sql(
        "SELECT bank_id, method, as_of, ewma_success, decay_rate, changepoint_flag, sample_n "
        "FROM bank_health_snapshots ORDER BY as_of",
        engine,
        parse_dates=["as_of"],
    )
