"""Pydantic response contracts for the Control Room + evidence API, per
docs/02-ARCHITECTURE.md "`api/` — FastAPI": "Thin. Serves the queue, streams a live batch
run over SSE, exposes audit records, proxies Razorpay test-mode calls. No business logic
— it calls `agent/`." and "## Module contracts": "Modules communicate through Pydantic
models only — no shared mutable state."

Every model here is a read-only *view* onto an `agent/` dataclass (`Decision`,
`DecisionContext`, `MandateResult`) — `api/converters.py` owns the mapping. No model in
this file is ever constructed by `agent/` code directly, so `agent/` never imports
`fastapi`/`pydantic` for its own decision logic (only `agent/context.py`'s plain
dataclasses do, kept that way deliberately).
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class RupeeMathOut(BaseModel):
    p_success: float
    amount: float
    p_revoke: float
    ltv_remaining: float
    cost: float
    expected_net: float


class RejectedAlternativeOut(BaseModel):
    description: str
    expected_net: float
    reason: str


class ClauseRefOut(BaseModel):
    id: str
    citation: str


class ActionOut(BaseModel):
    """A flattened view of `agent/actions.py`'s closed `Action` union — `action_type`
    names which dataclass it was (`schedule_debit` / `offer_date_change` / `stop` /
    `abstain` / `escalate_to_human`), and only the fields that action carries are
    non-null. A discriminated union would be more idiomatic, but this is a read-only
    audit view, not a request body the API needs to validate structurally — a flat shape
    is simpler for the frontend to render without a six-way type switch.
    """

    action_type: str
    scheduled_at: datetime | None = None
    channel: str | None = None
    notice_at: datetime | None = None
    new_preferred_day: int | None = None
    stop_reason: str | None = None
    abstain_reason: str | None = None
    escalate_reason: str | None = None


class DecisionOut(BaseModel):
    mandate_id: int
    cycle_index: int
    attempt_index: int
    bank_id: str
    method: str
    amount: float
    now: datetime
    chosen: ActionOut
    expected_net: float
    confidence_band: tuple[float, float]
    rejected_alternatives: list[RejectedAlternativeOut]
    clauses_satisfied: list[ClauseRefOut]
    clauses_blocked: list[ClauseRefOut]
    rupee_math: RupeeMathOut
    model_versions: dict[str, str]
    stopping_reason: str | None
    requires_signoff: bool
    audit_text: str = Field(
        description="agent/audit.py::render()'s SAW/THOUGHT/ALT/GATE/DID/WHY block"
    )


class QueueItemOut(BaseModel):
    """One row in the Control Room's at-risk case queue, ranked by `amount` — the queue
    itself is just every mandate's most recent decision, `/queue` sorts by amount
    descending per docs/08-FRONTEND-SPEC.md "Case queue, ranked by ₹ at risk"."""

    mandate_id: int
    bank_id: str
    method: str
    merchant_category: str
    amount: float
    is_cold_start: bool
    regime_shift_bank: bool
    decision: DecisionOut


class CounterOut(BaseModel):
    """Header counters for the Control Room, per docs/08-FRONTEND-SPEC.md: "₹ at risk →
    ₹ recovered → ₹ net LTV → notifications sent → revocations avoided → attempts *not*
    made." Computed from `MandateResult` totals across the demo batch, not from the
    streamed decisions alone (a decision doesn't carry the realized outcome)."""

    n_mandates: int
    amount_at_risk_inr: float
    gross_recovered_inr: float
    net_ltv_inr: float
    notifications_sent: int
    revocations: int
    attempts_not_made: int = Field(description="sum of n_abstentions across the batch")
    comparison_aggressive_8x_gross_recovered_inr: float
    comparison_aggressive_8x_net_ltv_inr: float
    comparison_aggressive_8x_revocations: int


class BatchEventOut(BaseModel):
    """One SSE event: either a `decision` (the next case in the streamed queue) or a
    final `counters` snapshot marking the batch complete."""

    event_type: str  # "decision" | "counters" | "done"
    decision: QueueItemOut | None = None
    counters: CounterOut | None = None


class RazorpayStatusOut(BaseModel):
    configured: bool
    key_id_prefix: str | None = None
    note: str


class RazorpaySubscriptionOut(BaseModel):
    id: str
    status: str
    plan_id: str
    customer_notify: bool
    short_url: str | None = None
    raw: dict[str, object] = Field(
        description="the unmodified Razorpay API response, for the audit trail"
    )


class RazorpayWebhookAckOut(BaseModel):
    received: bool
    event: str | None = None
    verified: bool
