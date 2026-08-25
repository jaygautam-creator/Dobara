"""Shared types for the decision layer: `DecisionContext` (everything `decide()` needs,
pre-fetched by the caller so `decide()` itself performs no I/O — see docs/06-AGENT-SPEC.md
"`agent/decide.py` is a **pure function**"), `RupeeMath`, `RejectedAlternative`,
`ClauseRef` and `Decision`.

`DecisionContext` deliberately mirrors the observable (non-latent) history a real PSP
would have: the same fields `features/recovery.py::build_recovery_features` and
`features/hazard.py::build_hazard_features` compute from the DB for historical rows, just
supplied directly instead of queried. This keeps the leakage discipline identical at
decision time even though there is no "future" to leak from at a live decision point.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING

from agent.stopping import StoppingReason

if TYPE_CHECKING:
    from agent.actions import Action

# Rupees. A type alias, not a wrapper class — this project prices attempts in plain
# float INR throughout (`sim/params.yaml`, `models/ltv.py`); a dedicated Money class
# would add ceremony without changing any arithmetic or catching any bug a float doesn't.
Money = float


@dataclass(frozen=True)
class DecisionContext:
    # Identity
    mandate_id: int
    cycle_id: int
    cycle_index: int  # mandate_age_cycles = cycle_index - 1, per features/recovery.py
    merchant_category: str
    bank_id: str
    method: str
    amount: Money
    afa_threshold_applicable: bool  # Mandate.afa_threshold_applicable — already AFA-registered

    # Timing — `now` is a supplied value, never `datetime.now()`, so `decide()` has no clock
    now: datetime
    cycle_due_date: datetime
    cycle_end: datetime

    # History (Tier 2 — our own past interactions with this mandate)
    attempt_index: int  # index of the attempt this decision would schedule
    last_attempt_at: datetime | None
    last_attempt_outcome: str | None  # one of sim.schema.ATTEMPT_OUTCOMES, or None
    n_attempts_to_date: int
    n_successes_to_date: int
    prior_failures_this_cycle: int
    consecutive_failed_cycles: int
    prev_error_source: str | None
    prev_error_step: str | None
    prev_error_reason: str | None

    # Hazard exposure history (Tier 2)
    failure_notifications_this_cycle: int
    total_contacts_30d: int
    days_since_first_failure_this_cycle: int
    has_customer_engaged_with_notice: bool

    # Fatigue / cost tracking this cycle
    notifications_sent_this_cycle: int
    notification_cost_spent_this_cycle_inr: Money
    last_pdn_sent_at: datetime | None

    # Declared (Tier 1)
    has_declared_preferred_day: bool
    declared_preferred_day: int | None

    # Date-change / DOBARA-CONVERGE
    date_change_last_offered_cycle_index: int | None

    # Terminal state
    customer_opted_out: bool
    mandate_revoked: bool


@dataclass(frozen=True)
class ClauseRef:
    id: str
    citation: str


@dataclass(frozen=True)
class RupeeMath:
    """Every term in `E[net|a] = P(success)*amount - P(revoke)*LTV_remaining -
    cost(channel,retry)`, shown — never a bare number (docs/06-AGENT-SPEC.md audit block)."""

    p_success: float
    amount: Money
    p_revoke: float
    ltv_remaining: Money
    cost: Money
    expected_net: Money


@dataclass(frozen=True)
class RejectedAlternative:
    """The audit-trail differentiator: what was considered and declined, with its own
    arithmetic — not just what was chosen."""

    description: str
    expected_net: Money
    reason: str


@dataclass(frozen=True)
class Decision:
    """`confidence_band` is `agent/decide.py`'s per-decision Wilson-interval-derived
    uncertainty band on `expected_net` — an approximation, not a posterior, and
    statistically unrelated to the bootstrap/seed-variance confidence intervals Phase 4's
    evaluation harness reports. Deliberately named differently from "CI" so the two are
    never conflated in an audit card or on /evidence. See docs/DECISIONS.md [2026-08-25]
    "confidence_interval renamed to confidence_band".
    """

    chosen: Action
    expected_net: Money
    confidence_band: tuple[Money, Money]
    rejected_alternatives: list[RejectedAlternative]
    clauses_satisfied: list[ClauseRef]
    clauses_blocked: list[ClauseRef]
    rupee_math: RupeeMath
    model_versions: dict[str, str]
    feature_attribution: dict[str, float]
    stopping_reason: StoppingReason | None
    requires_signoff: bool
