"""The bounded action set — a closed union of dataclasses. Nothing outside it is
representable as an `Action`, per docs/02-ARCHITECTURE.md "## The bounded action set".

**`ScheduleDebit` cannot be constructed without a `notice`.** Every debit attempt
requires its own pre-debit notification at least 24h earlier (rule `RBI-PDN-24H`,
docs/01-REGULATORY.md) — rather than checking that as a predicate that could be forgotten,
the type itself makes a bare debit-without-notice unrepresentable. This is the literal
reading of docs/06-AGENT-SPEC.md's "structural enforcement, not advisory": the compliance
gate (`agent/compliance.py`) still verifies the timing/content of that notice, but the
*existence* of one is enforced by the shape of the data, not by a rule that runs after
the fact.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum, StrEnum

from agent.stopping import StoppingReason


class Channel(StrEnum):
    SMS = "sms"
    WHATSAPP = "whatsapp"
    PUSH = "push"


class AbstentionReason(Enum):
    """The four abstention triggers named in docs/06-AGENT-SPEC.md "## Abstention"."""

    INSUFFICIENT_SLICE_N = "insufficient_slice_n"
    BANK_HEALTH_CHANGEPOINT = "bank_health_changepoint"
    SLICE_CALIBRATION_ERROR = "slice_calibration_error"
    EXPECTED_VALUE_CI_STRADDLES_ZERO = "expected_value_ci_straddles_zero"


@dataclass(frozen=True)
class SendPreDebitNotice:
    """The mandated pre-debit notification (`RBI-PDN-24H`). `contained_defer_option` and
    `contained_optout_option` default `True` because the agent's own templates always
    carry both (`RBI-PDN-OPTOUT`) — a candidate that didn't would have to construct this
    dataclass with an explicit `False`, which `agent/decide.py`'s candidate generation
    never does.
    """

    t: datetime
    channel: Channel
    template_id: str
    contained_defer_option: bool = True
    contained_optout_option: bool = True


@dataclass(frozen=True)
class ScheduleDebit:
    """Propose a debit at `t`. `notice` is the pre-debit notification that legally must
    precede it by >=24h — see module docstring. `afa_confirmed` records whether the
    mandate is already AFA-registered (`Mandate.afa_threshold_applicable`), checked by
    the compliance gate against the amount (`RBI-AFA-15K`).
    """

    t: datetime
    notice: SendPreDebitNotice
    afa_confirmed: bool


@dataclass(frozen=True)
class OfferDateChange:
    """Ask, at most once per `config.converge_min_cycles_between_date_changes` cycles
    (`DOBARA-CONVERGE`, SOFT), to move the mandate's recurring debit date."""

    t: datetime
    channel: Channel
    template_id: str
    new_preferred_day: int


@dataclass(frozen=True)
class EscalateToHuman:
    reason: str


@dataclass(frozen=True)
class Stop:
    reason: StoppingReason


@dataclass(frozen=True)
class Abstain:
    reason: AbstentionReason


Action = ScheduleDebit | SendPreDebitNotice | OfferDateChange | EscalateToHuman | Stop | Abstain
