from __future__ import annotations

import hashlib
from pathlib import Path

from sim.engine import run_simulation
from sim.params import load_params
from sim.schema import ATTEMPT_OUTCOMES


def _small_run(tmp_path: Path, seed: int) -> Path:
    params = load_params()
    db_path = tmp_path / f"seed{seed}.sqlite3"
    run_simulation(
        params, seed=seed, db_path=str(db_path), n_customers=60, n_cycles=4, n_merchants=5
    )
    return db_path


def test_sim_is_reproducible_from_seed(tmp_path: Path) -> None:
    a = _small_run(tmp_path, seed=7)
    b = _small_run(tmp_path, seed=7)
    hash_a = hashlib.sha256(a.read_bytes()).hexdigest()
    hash_b = hashlib.sha256(b.read_bytes()).hexdigest()
    assert hash_a == hash_b


def test_different_seeds_diverge(tmp_path: Path) -> None:
    a = _small_run(tmp_path, seed=1)
    b = _small_run(tmp_path, seed=2)
    hash_a = hashlib.sha256(a.read_bytes()).hexdigest()
    hash_b = hashlib.sha256(b.read_bytes()).hexdigest()
    assert hash_a != hash_b


def test_summary_produces_plausible_rates(tmp_path: Path) -> None:
    params = load_params()
    db_path = tmp_path / "summary.sqlite3"
    summary = run_simulation(
        params, seed=3, db_path=str(db_path), n_customers=300, n_cycles=8, n_merchants=10
    )
    assert summary.n_attempts > 0
    assert 0.0 <= summary.failure_rate <= 1.0
    assert 0.0 <= summary.recovery_rate <= 1.0
    assert summary.monthly_revocation_ratio >= 0.0


def test_rejected_no_pdn_outcome_is_reachable() -> None:
    """A retry lacking a valid PDN is rejected outright, not soft-declined."""
    import numpy as np

    from sim.engine import attempt_outcome
    from sim.latent import build_bank_latents, build_dated_outages, sample_customer_latents

    params = load_params()
    rng = np.random.default_rng(0)
    banks = build_bank_latents(params)
    outages = build_dated_outages(params)
    customer = sample_customer_latents(params, 1, rng)[0]
    bank = banks[customer.bank_id]

    from datetime import datetime

    draw = attempt_outcome(
        bank,
        customer,
        datetime(2026, 3, 1),
        499.0,
        has_valid_pdn=False,
        params=params,
        dated_outages=outages,
        rng=rng,
    )
    assert draw.outcome == "rejected_no_pdn"
    assert draw.outcome in ATTEMPT_OUTCOMES
