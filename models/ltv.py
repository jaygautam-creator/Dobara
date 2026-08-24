"""LTV estimator. `LTV_remaining = amount x expected_remaining_cycles x margin_factor`.
Per docs/05-ML-SPEC.md: deliberately simple and transparent, **not** a learned model — an
opaque LTV estimate would undermine the audit story, since it multiplies the downside term
in the agent's `E[net]` decision.

`expected_remaining_cycles` comes from a Kaplan-Meier-style discrete-time life table of
mandate survival by `(merchant_category, mandate_age_cycles)`, built directly from the
simulated `Mandate`/`Cycle`/`Revocation` tables — not from the hazard model's predictions.
This is intentionally a different, simpler estimate than `models/hazard.py`'s per-attempt
hazard: the life table answers "how many more cycles will this mandate likely survive,"
the hazard model answers "how risky is retrying right now."

`margin_factor` is a declared assumption (`sim/params.yaml` `ltv.margin_factor`) — its
range is required to feed the Phase 4 sensitivity analysis, because the headline
net-LTV conclusion depends on it.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd
from sqlalchemy import create_engine

from sim.params import Params


def _load_mandate_life_data(db_path: str) -> pd.DataFrame:
    """One row per mandate: how many cycles it reached, its category, and whether (and at
    what cycle) it was revoked. `n_cycles_reached` = the highest `cycle_index` the mandate
    has any `Cycle` row for — i.e. it was "at risk" for every age up to and including that.
    """
    engine = create_engine(f"sqlite:///{db_path}")
    query = """
    SELECT
        m.id AS mandate_id,
        mer.category AS merchant_category,
        MAX(cy.cycle_index) AS n_cycles_reached,
        m.status
    FROM mandates m
    JOIN merchants mer ON m.merchant_id = mer.id
    JOIN cycles cy ON cy.mandate_id = m.id
    GROUP BY m.id, mer.category, m.status
    """
    df = pd.read_sql(query, engine)
    revoked = pd.read_sql(
        """
        SELECT m.id AS mandate_id, cy.cycle_index AS revoked_at_cycle
        FROM revocations r
        JOIN mandates m ON r.mandate_id = m.id
        JOIN attempts a ON r.trigger_attempt_id = a.id
        JOIN cycles cy ON a.cycle_id = cy.id
        """,
        engine,
    )
    return df.merge(revoked, on="mandate_id", how="left")


@dataclass(frozen=True)
class LifeTable:
    """`survival[(category, age)]` = P(mandate of this category survives past `age`
    cycles without revocation). `survival[(category, 0)] == 1.0` by construction.
    """

    survival: dict[tuple[str, int], float]
    horizon_cycles: int


def build_life_table(db_path: str, horizon_cycles: int) -> LifeTable:
    mandates = _load_mandate_life_data(db_path)
    survival: dict[tuple[str, int], float] = {}

    for category, g in mandates.groupby("merchant_category"):
        s = 1.0
        survival[(str(category), 0)] = 1.0
        for age in range(1, horizon_cycles + 1):
            at_risk = g[g["n_cycles_reached"] >= age]
            n_at_risk = len(at_risk)
            n_revoked_this_age = int((at_risk["revoked_at_cycle"] == age).sum())
            hazard = n_revoked_this_age / n_at_risk if n_at_risk else 0.0
            s *= 1 - hazard
            survival[(str(category), age)] = s

    return LifeTable(survival=survival, horizon_cycles=horizon_cycles)


def expected_remaining_cycles(table: LifeTable, category: str, current_age: int) -> float:
    """Sum of S(k)/S(current_age) for k = current_age+1 .. horizon — the standard
    discrete-time life-table expected-remaining-periods-within-horizon formula.
    """
    s_now = table.survival.get((category, current_age))
    if s_now is None or s_now == 0.0:
        return 0.0
    total = 0.0
    for k in range(current_age + 1, table.horizon_cycles + 1):
        s_k = table.survival.get((category, k), 0.0)
        total += s_k / s_now
    return total


def ltv_remaining(
    amount: float, table: LifeTable, category: str, current_age: int, params: Params
) -> float:
    margin_factor = float(params.get("ltv.margin_factor"))
    remaining_cycles = expected_remaining_cycles(table, category, current_age)
    return amount * remaining_cycles * margin_factor
