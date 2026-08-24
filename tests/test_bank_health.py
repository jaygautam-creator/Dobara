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
