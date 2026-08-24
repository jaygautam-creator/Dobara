from __future__ import annotations

from pathlib import Path

from models.ltv import build_life_table, expected_remaining_cycles, ltv_remaining
from sim.engine import run_simulation
from sim.params import load_params


def test_life_table_survival_is_non_increasing_with_age(tmp_path: Path) -> None:
    params = load_params()
    db_path = tmp_path / "ltv.sqlite3"
    run_simulation(
        params, seed=42, db_path=str(db_path), n_customers=3000, n_cycles=8, n_merchants=15
    )

    table = build_life_table(str(db_path), horizon_cycles=8)
    categories = {cat for cat, _ in table.survival}
    assert categories

    for cat in categories:
        values = [table.survival[(cat, age)] for age in range(9)]
        assert values[0] == 1.0
        assert all(a >= b - 1e-9 for a, b in zip(values, values[1:], strict=False))
        assert all(0.0 <= v <= 1.0 for v in values)


def test_expected_remaining_cycles_decreases_with_age(tmp_path: Path) -> None:
    params = load_params()
    db_path = tmp_path / "ltv2.sqlite3"
    run_simulation(
        params, seed=7, db_path=str(db_path), n_customers=3000, n_cycles=8, n_merchants=15
    )
    table = build_life_table(str(db_path), horizon_cycles=8)
    cat = next(iter({c for c, _ in table.survival}))

    remaining_at_0 = expected_remaining_cycles(table, cat, 0)
    remaining_at_6 = expected_remaining_cycles(table, cat, 6)
    assert remaining_at_0 > remaining_at_6 >= 0
    assert expected_remaining_cycles(table, cat, 8) == 0.0  # nothing left past the horizon


def test_ltv_remaining_scales_with_amount_and_margin(tmp_path: Path) -> None:
    params = load_params()
    db_path = tmp_path / "ltv3.sqlite3"
    run_simulation(
        params, seed=3, db_path=str(db_path), n_customers=3000, n_cycles=8, n_merchants=15
    )
    table = build_life_table(str(db_path), horizon_cycles=8)
    cat = next(iter({c for c, _ in table.survival}))

    ltv_low_amount = ltv_remaining(100.0, table, cat, 1, params)
    ltv_high_amount = ltv_remaining(1000.0, table, cat, 1, params)
    assert ltv_high_amount > ltv_low_amount
    assert ltv_high_amount == ltv_low_amount * 10  # linear in amount by construction
