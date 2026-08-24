"""The real calibration gate. `sim/run.py`'s BENCHMARKS dict only prints per-seed for
human eyeballing during `make sim` — it never fails. This test runs the default-scale
simulation across 5 seeds and asserts the MEAN of each metric lands inside the declared
band, allowing per-seed variance. CI fails if calibration regresses.

`revocation_per_execution_ratio` is the harder benchmark, derived from two figures already
pinned in docs/04-DATA-MODEL.md (20M revocations/month, 808M executions/month) rather than
borrowed dunning-benchmark bands: it jointly constrains failure_rate and P(revoke |
failure) — the exact product the thesis depends on. Treated as a target ratio with
caveats (see sim/params.yaml's revocation block), not a precision constant.
"""

from __future__ import annotations

import statistics

import pytest

from sim.engine import run_simulation
from sim.params import load_params
from sim.run import BENCHMARKS

SEEDS = [0, 1, 2, 3, 4]


@pytest.fixture(scope="module")
def five_seed_summaries(tmp_path_factory: pytest.TempPathFactory) -> list:
    params = load_params()
    tmp_dir = tmp_path_factory.mktemp("calibration")
    summaries = []
    for seed in SEEDS:
        db_path = tmp_dir / f"seed{seed}.sqlite3"
        summaries.append(run_simulation(params, seed=seed, db_path=str(db_path)))
    return summaries


@pytest.mark.parametrize("metric", list(BENCHMARKS.keys()))
def test_mean_metric_across_seeds_in_benchmark_band(five_seed_summaries: list, metric: str) -> None:
    lo, hi = BENCHMARKS[metric]
    values = [getattr(s, metric) for s in five_seed_summaries]
    mean = statistics.mean(values)
    assert lo <= mean <= hi, (
        f"{metric}: mean {mean:.4f} over seeds {SEEDS} outside benchmark band [{lo}, {hi}]. "
        f"Per-seed values: {[round(v, 4) for v in values]}. "
        "This is a calibration regression — see docs/04-DATA-MODEL.md and sim/params.yaml."
    )
