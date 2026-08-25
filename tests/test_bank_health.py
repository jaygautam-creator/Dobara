from __future__ import annotations

from pathlib import Path

from models.bank_health import compute_bank_health_snapshots, load_snapshots
from sim.engine import run_simulation
from sim.params import load_params


def test_snapshots_written_and_asof_ordered(tmp_path: Path) -> None:
    params = load_params()
    db_path = tmp_path / "bh.sqlite3"
    summary = run_simulation(
        params, seed=11, db_path=str(db_path), n_customers=200, n_cycles=4, n_merchants=5
    )

    written = compute_bank_health_snapshots(str(db_path))
    assert written == summary.n_attempts

    snapshots = load_snapshots(str(db_path))
    assert len(snapshots) == written
    assert snapshots["as_of"].is_monotonic_increasing
    assert snapshots["ewma_success"].between(0, 1).all()
    assert snapshots["decay_rate"].between(0.05, 0.35).all()


def test_ewma_tracks_a_degrading_series() -> None:
    from collections import deque

    from models.bank_health import _SeriesState, update_ewma

    state = _SeriesState(ewma=0.9, recent_outcomes=deque(maxlen=10))
    for _ in range(20):
        update_ewma(state, success=True)
    high = state.ewma
    for _ in range(20):
        update_ewma(state, success=False)
    low = state.ewma
    assert low < high
    assert low < 0.5


def test_changepoint_low_false_positive_rate_on_a_stable_series() -> None:
    """Regression guard for the 2026-08-25 recalibration (see the module docstring and
    docs/DECISIONS.md): the detector must stay quiet on a series with no real shift,
    across many independent stable series, not just one lucky draw.
    """
    import random

    from models.bank_health import (
        BASELINE_N,
        RECENT_N,
        _SeriesState,
        detect_changepoint,
        update_ewma,
    )

    n_flagged = 0
    n_series = 20
    for series_seed in range(n_series):
        rng = random.Random(series_seed)
        state = _SeriesState()
        flagged_this_series = False
        for _ in range(BASELINE_N + RECENT_N * 3):
            success = rng.random() < 0.85  # one stable true rate throughout
            update_ewma(state, success, is_first_attempt=True)
            if detect_changepoint(state):
                flagged_this_series = True
        if flagged_this_series:
            n_flagged += 1
    # Old detector's false-positive rate was ~15% per snapshot; the recalibrated one
    # should almost never flag a series that never actually shifted.
    assert n_flagged <= 2, f"{n_flagged}/{n_series} stable series flagged a changepoint"


def test_changepoint_detects_a_sustained_shift() -> None:
    """Mirrors the real regime-shift mechanism (sim/params.yaml's regime_shift block):
    a bank's success rate drops and STAYS down. The detector must catch it and keep
    flagging for the remainder of the shifted period, not just the moment of transition
    (the property the old split-half rolling-window design structurally lacked).
    """
    import random

    from models.bank_health import (
        BASELINE_N,
        RECENT_N,
        _SeriesState,
        detect_changepoint,
        update_ewma,
    )

    rng = random.Random(42)
    state = _SeriesState()
    for _ in range(BASELINE_N):
        update_ewma(state, rng.random() < 0.85, is_first_attempt=True)
    assert not detect_changepoint(state)  # baseline alone, no shift yet

    n_post_shift = RECENT_N * 3
    n_flagged = 0
    for i in range(n_post_shift):
        # A clear, unambiguous drop (0.85 -> 0.55) -- this test is a regression guard on
        # detection *working at all*, not a precise replay of the real, noisier
        # regime-shift magnitude (see docs/DECISIONS.md for the real-data validation,
        # which is inherently burstier/easier to detect than this clean i.i.d. draw).
        update_ewma(state, rng.random() < 0.55, is_first_attempt=True)
        if i >= RECENT_N and detect_changepoint(state):  # give the recent window time to fill
            n_flagged += 1
    checked = n_post_shift - RECENT_N
    assert n_flagged / checked > 0.9, f"only {n_flagged}/{checked} post-shift checks flagged"
