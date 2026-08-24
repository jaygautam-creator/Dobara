"""The leakage boundary for Model 2 (revocation hazard). Per docs/05-ML-SPEC.md, the
formulation is discrete-time hazard on person-period data: one row per unit of exposure,
target = revoked at that unit.

**Exposure unit, and why it is per-`soft_decline`-attempt rather than per-calendar-day.**
The ML spec describes "one row per mandate per day at risk." A daily grid is the right
shape when the underlying hazard process can fire on any day. In this simulator it
cannot: `sim/engine.py` evaluates `revocation_hazard()` **only** immediately after a
`soft_decline` outcome — never on a `hard_decline` (that ends the cycle without a hazard
check), never on a day with no attempt at all. A daily grid would therefore be mostly
structurally-zero rows carrying no information, and including `hard_decline` attempts as
exposure rows would inject always-negative-label rows that dilute the dataset without
representing a real point of risk. The unit of exposure here is **one row per
`soft_decline` attempt** — the actual decision point where the simulator's hazard is
evaluated. If a future simulator version adds calendar-day-driven hazard (e.g. decay of an
old failure's effect independent of the next attempt), this module is where the grid
would need to widen.

**No import of `sim.latent` anywhere in this package** — enforced by
`tests/test_latent_isolation.py`. **No feature may encode individual balance or income**
— enforced by `assert_no_banned_features` (shared with `features/recovery.py`).
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

import pandas as pd
from sqlalchemy import create_engine

from features.recovery import BANNED_FEATURE_SUBSTRINGS, assert_no_banned_features
from sim.splits import split_for_cycle

HAZARD_FEATURE_COLUMNS = [
    "failure_notifications_this_cycle",
    "total_contacts_30d",
    "days_since_first_failure_this_cycle",
    "consecutive_failed_cycles",
    "mandate_age_cycles",
    "amount_band",  # cohort band, not individual — see docs/05-ML-SPEC.md
    "method",
    "merchant_category",
    "has_customer_engaged_with_notice",
]

LABEL_COLUMN = "label_revoked"

assert_no_banned_features(HAZARD_FEATURE_COLUMNS)


def _amount_band(amount: float) -> str:
    """Cohort band, not a continuous individual amount — deliberately coarse."""
    if amount < 250:
        return "under_250"
    if amount < 750:
        return "250_750"
    if amount < 2000:
        return "750_2000"
    return "over_2000"


@dataclass
class _MandateHazardHistory:
    current_cycle_id: int | None = None
    failure_notifications_this_cycle: int = 0
    first_failure_at_this_cycle: pd.Timestamp | None = None
    consecutive_failed_cycles: int = 0
    cycle_had_success: bool = False
    contacts_30d: list[pd.Timestamp] = field(default_factory=list)


def _on_cycle_transition(h: _MandateHazardHistory, new_cycle_id: int) -> None:
    if h.current_cycle_id is not None:
        h.consecutive_failed_cycles = 0 if h.cycle_had_success else h.consecutive_failed_cycles + 1
    h.current_cycle_id = new_cycle_id
    h.failure_notifications_this_cycle = 0
    h.first_failure_at_this_cycle = None
    h.cycle_had_success = False


def _load_raw(db_path: str) -> pd.DataFrame:
    """All attempts (not just failures) — needed to track cycle-level success correctly
    for `consecutive_failed_cycles`, even though only `soft_decline` rows are emitted as
    exposure units.
    """
    engine = create_engine(f"sqlite:///{db_path}")
    query = """
    SELECT
        a.id AS attempt_id,
        a.cycle_id,
        a.scheduled_at,
        a.outcome,
        m.id AS mandate_id,
        m.amount,
        m.method,
        m.is_cold_start,
        m.regime_shift_bank,
        mer.category AS merchant_category,
        cy.cycle_index,
        r.trigger_attempt_id
    FROM attempts a
    JOIN cycles cy ON a.cycle_id = cy.id
    JOIN mandates m ON cy.mandate_id = m.id
    JOIN merchants mer ON m.merchant_id = mer.id
    LEFT JOIN revocations r ON r.trigger_attempt_id = a.id
    ORDER BY a.scheduled_at, a.id
    """
    return pd.read_sql(query, engine, parse_dates=["scheduled_at"])


def build_hazard_features(db_path: str) -> pd.DataFrame:
    """One row per `soft_decline` attempt (the exposure unit — see module docstring).
    Features computed strictly from data available before/at that attempt's
    `scheduled_at`: prior failures and contacts on the *same* mandate. Label is 1 iff this
    exact attempt is the `trigger_attempt_id` of a `Revocation`, 0 otherwise.
    """
    raw = _load_raw(db_path)
    rows: list[dict[str, object]] = []
    histories: dict[int, _MandateHazardHistory] = defaultdict(_MandateHazardHistory)

    for row in raw.itertuples(index=False):
        h = histories[row.mandate_id]
        if h.current_cycle_id != row.cycle_id:
            _on_cycle_transition(h, row.cycle_id)

        if row.outcome == "success":
            h.cycle_had_success = True
            continue
        if row.outcome != "soft_decline":
            continue  # hard_decline and rejected_no_pdn never reach revocation_hazard()

        cutoff = row.scheduled_at - pd.Timedelta(days=30)
        h.contacts_30d = [t for t in h.contacts_30d if t >= cutoff]
        total_contacts_30d = len(h.contacts_30d)

        days_since_first_failure = (
            (row.scheduled_at - h.first_failure_at_this_cycle).days
            if h.first_failure_at_this_cycle is not None
            else 0
        )

        rows.append(
            {
                "attempt_id": row.attempt_id,
                "mandate_id": row.mandate_id,
                "failure_notifications_this_cycle": h.failure_notifications_this_cycle,
                "total_contacts_30d": total_contacts_30d,
                "days_since_first_failure_this_cycle": days_since_first_failure,
                "consecutive_failed_cycles": h.consecutive_failed_cycles,
                "mandate_age_cycles": row.cycle_index - 1,
                "amount_band": _amount_band(row.amount),
                "method": row.method,
                "merchant_category": row.merchant_category,
                # no notification-response tracking on the pre-debit notice itself in
                # sim v1 (only the date-change OFFER records a response) — always False,
                # a known simplification, not a fabricated signal
                "has_customer_engaged_with_notice": False,
                LABEL_COLUMN: row.trigger_attempt_id == row.attempt_id,
                "cycle_index": row.cycle_index,
                "is_cold_start": bool(row.is_cold_start),
                "regime_shift_bank": bool(row.regime_shift_bank),
            }
        )

        # update history AFTER emitting this row's features — never before
        h.failure_notifications_this_cycle += 1
        if h.first_failure_at_this_cycle is None:
            h.first_failure_at_this_cycle = row.scheduled_at
        h.contacts_30d.append(row.scheduled_at)

    df = pd.DataFrame(rows)
    assert_no_banned_features(list(df.columns))
    df["split"] = [
        split_for_cycle(int(ci), bool(cs))
        for ci, cs in zip(df["cycle_index"], df["is_cold_start"], strict=True)
    ]
    return df


__all__ = [
    "HAZARD_FEATURE_COLUMNS",
    "LABEL_COLUMN",
    "BANNED_FEATURE_SUBSTRINGS",
    "build_hazard_features",
]
