"""Non-latent SQLAlchemy schema. Everything here is information a real PSP would actually
see. Latent (hidden) tables live in `sim/latent.py`, isolated by an import-boundary test
(`tests/test_latent_isolation.py`) — `features/` must never import that module.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Merchant(Base):
    __tablename__ = "merchants"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    category: Mapped[str] = mapped_column(String(40))
    arpu_band: Mapped[str] = mapped_column(String(20))
    avg_ticket: Mapped[float]


class Customer(Base):
    __tablename__ = "customers"

    id: Mapped[int] = mapped_column(primary_key=True)
    bank_id: Mapped[str] = mapped_column(String(10))
    segment: Mapped[str] = mapped_column(String(20))
    preferred_debit_day: Mapped[int | None]
    opted_out: Mapped[bool] = mapped_column(default=False)


class Mandate(Base):
    __tablename__ = "mandates"

    id: Mapped[int] = mapped_column(primary_key=True)
    merchant_id: Mapped[int] = mapped_column(ForeignKey("merchants.id"))
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"))
    method: Mapped[str] = mapped_column(String(20), default="upi_autopay")
    amount: Mapped[float]
    cycle_day: Mapped[int]
    created_at: Mapped[datetime]
    status: Mapped[str] = mapped_column(String(20), default="active")
    afa_threshold_applicable: Mapped[bool]
    is_cold_start: Mapped[bool] = mapped_column(default=False)
    regime_shift_bank: Mapped[bool] = mapped_column(default=False)


class Cycle(Base):
    __tablename__ = "cycles"

    id: Mapped[int] = mapped_column(primary_key=True)
    mandate_id: Mapped[int] = mapped_column(ForeignKey("mandates.id"))
    cycle_index: Mapped[int]
    due_date: Mapped[datetime]
    status: Mapped[str] = mapped_column(String(20), default="pending")


# Attempt.outcome values. `rejected_no_pdn` is the value that makes the aggressive arm
# expensive: a retry without a valid pre-debit notification is rejected at the rail, not
# soft-declined. See docs/04-DATA-MODEL.md.
ATTEMPT_OUTCOMES = ("success", "soft_decline", "hard_decline", "rejected_no_pdn")


class Attempt(Base):
    __tablename__ = "attempts"

    id: Mapped[int] = mapped_column(primary_key=True)
    cycle_id: Mapped[int] = mapped_column(ForeignKey("cycles.id"))
    attempt_index: Mapped[int]
    scheduled_at: Mapped[datetime]
    executed_at: Mapped[datetime]
    outcome: Mapped[str] = mapped_column(String(20))
    error_source: Mapped[str | None] = mapped_column(String(20))
    error_step: Mapped[str | None] = mapped_column(String(30))
    error_reason: Mapped[str | None] = mapped_column(String(40))
    gateway_ref: Mapped[str] = mapped_column(String(40))
    had_valid_pdn: Mapped[bool]


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(primary_key=True)
    mandate_id: Mapped[int] = mapped_column(ForeignKey("mandates.id"))
    cycle_id: Mapped[int] = mapped_column(ForeignKey("cycles.id"))
    kind: Mapped[str] = mapped_column(String(20))  # pre_debit | post_confirm | date_change_offer
    channel: Mapped[str] = mapped_column(String(20))  # sms | whatsapp | push
    sent_at: Mapped[datetime]
    template_id: Mapped[str] = mapped_column(String(40))
    contained_defer_option: Mapped[bool] = mapped_column(default=False)
    customer_response: Mapped[str | None] = mapped_column(String(20))


class Revocation(Base):
    __tablename__ = "revocations"

    id: Mapped[int] = mapped_column(primary_key=True)
    mandate_id: Mapped[int] = mapped_column(ForeignKey("mandates.id"))
    revoked_at: Mapped[datetime]
    trigger_attempt_id: Mapped[int | None] = mapped_column(ForeignKey("attempts.id"))


class Decision(Base):
    __tablename__ = "decisions"

    id: Mapped[int] = mapped_column(primary_key=True)
    cycle_id: Mapped[int] = mapped_column(ForeignKey("cycles.id"))
    decided_at: Mapped[datetime]
    chosen_action: Mapped[str] = mapped_column(String(40))
    expected_net: Mapped[float]
    model_versions: Mapped[str]  # JSON
    rejected_alternatives_json: Mapped[str]
    clauses_json: Mapped[str]
    rupee_math_json: Mapped[str]
    stopping_reason: Mapped[str | None] = mapped_column(String(40))
    confidence_band_json: Mapped[str]  # agent's per-decision Wilson band, not an eval CI


class BankHealthSnapshot(Base):
    __tablename__ = "bank_health_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True)
    bank_id: Mapped[str] = mapped_column(String(10))
    method: Mapped[str] = mapped_column(String(20))
    as_of: Mapped[datetime]
    ewma_success: Mapped[float]
    decay_rate: Mapped[float]
    changepoint_flag: Mapped[bool]
    sample_n: Mapped[int]
