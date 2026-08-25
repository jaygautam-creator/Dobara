"""Model 3 — Bank Health. EWMA of debit success per (bank x method) with an adaptive
decay rate (decay accelerates when recent variance rises), plus a change-point flag.
Not learned end-to-end — a transparent statistical estimator, deliberately, per
docs/05-ML-SPEC.md, echoing Razorpay's published dynamic module (Bygari et al., IEEE Big
Data 2021).

Writes one `BankHealthSnapshot` row per (bank, method) after each attempt, so
`features/build.py` can as-of join against a snapshot strictly before the decision
timestamp — never the snapshot that includes the current attempt's own outcome.

**Change-point detector, recalibrated 2026-08-25** — see docs/DECISIONS.md for the full
empirical validation. The original design (split a 16-attempt rolling window in half,
flag a >0.20 absolute drop) was replaced for two independent reasons, both confirmed
against the real training data before this fix, not assumed:

1. **Statistically too loose.** At this simulator's realistic bank success rates
   (~80-90%), two independent 8-sample proportions differ by >=0.20 roughly 1 time in 7
   under pure noise (a 0.20 gap is only ~1.1 standard deviations at n=8), and this check
   reran after *every single attempt* — a repeated-significance-testing setup. Measured:
   the old detector fired 13-18% of the time on *every* bank, not concentrated on the
   one bank (`SBI`, `sim/params.yaml`'s `regime_shift.bank_id`) actually carrying an
   injected shift.
2. **The "split rolling window" design is structurally the wrong shape for this need.**
   Even widening the window and adding a proper two-sample z-test (tried first, see
   docs/DECISIONS.md) only detects the brief *moment* the window straddles a transition —
   once both halves of the window are past the boundary, they're both drawn from the
   *same* new regime and the test goes quiet again, even though the bank remains
   objectively shifted from what the models were trained on. The abstention use case
   (`agent/decide.py`) needs "is this bank still, right now, behaving differently than
   the population it was trained against," a *persistent* state, not a one-off event.

**Current design**: a **frozen early-history baseline** (`BASELINE_N` observations,
established once per (bank, method) series and never updated) compared by two-sample
proportion z-test against a **rolling recent window** (`RECENT_N` observations) that
keeps sliding for the life of the series. This persists correctly through a sustained
regime shift rather than firing once and resetting. Both windows are fed **first-attempt
outcomes only** (`attempt_index == 1`), not every attempt — retries within a cycle are
strongly outcome-correlated (`retry_policy.within_cycle_repeat_failure_correlation`,
`sim/params.yaml`), which inflates the *true* variance of a per-attempt stream well
beyond the i.i.d. binomial formula a z-test assumes; first-attempt-per-cycle events are
close to independent draws, which is what the test's variance estimate actually requires.
The EWMA (`ewma_success`) is unaffected — it still updates on every attempt, since it was
never the flagged mechanism. Empirically validated on `data/dobara.sqlite3` (seed 42):
`BASELINE_N=300`, `RECENT_N=100`, `CHANGEPOINT_Z_THRESHOLD=3.0` gives a ~0.2-0.5%
false-positive rate on the seven unaffected banks and 55-65% detection through cycles
6-8 for `SBI` specifically (vs. ~0% for `SBI` itself before its own cycle-6 shift) —
concentrated on the intended target, not noise. See `tests/test_bank_health.py`'s
`test_changepoint_*` cases for the regression guard.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from math import sqrt

import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from sim.schema import Attempt, BankHealthSnapshot, Customer, Cycle, Mandate

MIN_DECAY = 0.05
MAX_DECAY = 0.35
VARIANCE_WINDOW = 10

# Change-point detector: frozen baseline vs. rolling recent window, both fed
# first-attempt-only outcomes. See the module docstring for the empirical validation
# behind these three constants.
BASELINE_N = 300
RECENT_N = 100
CHANGEPOINT_Z_THRESHOLD = 3.0


@dataclass
class _SeriesState:
    ewma: float = 0.9  # neutral prior: most attempts succeed
    recent_outcomes: deque[int] = field(default_factory=lambda: deque(maxlen=VARIANCE_WINDOW))
    sample_n: int = 0
    # Change-point state, fed first-attempt-only outcomes (see module docstring).
    # `changepoint_baseline` is None while still accumulating, then frozen to (s, n) once
    # BASELINE_N first-attempt observations have been seen for this (bank, method).
    changepoint_baseline_acc: list[int] = field(default_factory=lambda: [0, 0])  # [s, n]
    changepoint_baseline: tuple[int, int] | None = None
    changepoint_recent: deque[int] = field(default_factory=lambda: deque(maxlen=RECENT_N))


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


def _update_changepoint_state(state: _SeriesState, success: bool) -> None:
    """Feeds one first-attempt outcome into the frozen-baseline/rolling-recent pair.
    Before the baseline is frozen, observations build it; once frozen, all further
    observations feed the (always-sliding) recent window instead.
    """
    if state.changepoint_baseline is None:
        state.changepoint_baseline_acc[0] += int(success)
        state.changepoint_baseline_acc[1] += 1
        if state.changepoint_baseline_acc[1] >= BASELINE_N:
            state.changepoint_baseline = (
                state.changepoint_baseline_acc[0],
                state.changepoint_baseline_acc[1],
            )
    else:
        state.changepoint_recent.append(int(success))


def detect_changepoint(state: _SeriesState) -> bool:
    """Two-sample proportion z-test: the frozen early-history baseline vs. the current
    rolling recent window. See the module docstring for why this shape (not a rolling
    split-half window) and why first-attempt-only (not every attempt).
    """
    if state.changepoint_baseline is None or len(state.changepoint_recent) < RECENT_N:
        return False
    s1, n1 = state.changepoint_baseline
    recent = list(state.changepoint_recent)
    s2, n2 = sum(recent), len(recent)
    p1, p2 = s1 / n1, s2 / n2
    p_pool = (s1 + s2) / (n1 + n2)
    se = sqrt(max(p_pool * (1 - p_pool) * (1 / n1 + 1 / n2), 1e-9))
    z = (p1 - p2) / se
    return z > CHANGEPOINT_Z_THRESHOLD


def update_ewma(state: _SeriesState, success: bool, is_first_attempt: bool = True) -> _SeriesState:
    decay = adaptive_decay_rate(state.recent_outcomes)
    state.ewma = decay * float(success) + (1 - decay) * state.ewma
    state.recent_outcomes.append(int(success))
    state.sample_n += 1
    if is_first_attempt:
        _update_changepoint_state(state, success)
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
                Attempt.attempt_index,
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
        for scheduled_at, outcome, attempt_index, method, bank_id in rows:
            key = (bank_id, method)
            state = states.setdefault(key, _SeriesState())
            success = outcome == "success"
            update_ewma(state, success, is_first_attempt=(attempt_index == 1))
            snapshot = BankHealthSnapshot(
                bank_id=bank_id,
                method=method,
                as_of=scheduled_at,
                ewma_success=state.ewma,
                decay_rate=adaptive_decay_rate(state.recent_outcomes),
                changepoint_flag=detect_changepoint(state),
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
