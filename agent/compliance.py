"""The declarative compliance rule engine. Every rule in docs/01-REGULATORY.md's
"## The rules, as executable constraints" table is implemented here as a `Rule` object
carrying `id`, `text`, `severity`, `citation`, `source_url`, `predicate`.

**Structural enforcement, not advisory** (docs/06-AGENT-SPEC.md). `agent/decide.py` calls
`is_hard_compliant()` *inside* candidate generation, before a candidate is ever added to
the pool that gets scored — a HARD-violating action is filtered out before it can be
chosen, not merely flagged afterwards. `evaluate()` still runs for every scored candidate
(not just the winner) so `clauses_satisfied` / `clauses_blocked` can be logged for
rejected alternatives too, per the audit trail's "considered and declined, with the
arithmetic" standard.

Several predicates below are honestly trivial — `True` by construction rather than a real
check against data this system doesn't model (no third-party contact, no free-text
messages, no execution-time confirmation step yet). Each is commented with *why* it's
trivial rather than left to look like a real check. See docs/01-REGULATORY.md's own
framing: turning regulation into code is the differentiator; pretending a no-op check is
a real one would undermine exactly that.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum

from agent.actions import Action, Channel, OfferDateChange, ScheduleDebit, SendPreDebitNotice
from agent.context import DecisionContext
from agent.policy import PolicyConfig
from features.recovery import assert_no_banned_features

AFA_THRESHOLD_INR = 15000.0
AFA_THRESHOLD_INR_INSURANCE_MF_CC = 100000.0
AFA_HIGH_THRESHOLD_CATEGORIES = {"insurance", "mutual_fund", "credit_card_bill"}

CONTACT_HOUR_START = 8
CONTACT_HOUR_END = 19

# The only templates candidate generation is ever allowed to construct
# (`agent/decide.py`) — the audit-block example in docs/06-AGENT-SPEC.md uses
# `tmpl_pdn_defer_v3`, reused here rather than inventing a parallel name.
TEMPLATE_PDN = "tmpl_pdn_defer_v3"
TEMPLATE_DATE_CHANGE = "tmpl_date_change_v1"
APPROVED_TEMPLATES: dict[Channel, set[str]] = {
    Channel.SMS: {TEMPLATE_PDN, TEMPLATE_DATE_CHANGE},
    Channel.WHATSAPP: {TEMPLATE_PDN, TEMPLATE_DATE_CHANGE},
    Channel.PUSH: {TEMPLATE_PDN, TEMPLATE_DATE_CHANGE},
}

# DPDP-MINIMISE is a name-based structural re-check (like
# `features/recovery.py::assert_no_banned_features`) against `DecisionContext`'s own
# field names, run once at import time — a static property of the type, not something
# that varies per call, so there's nothing to re-check per (action, ctx) pair.
assert_no_banned_features(list(DecisionContext.__dataclass_fields__.keys()))


class Severity(Enum):
    HARD = "hard"
    SOFT = "soft"


@dataclass(frozen=True)
class Rule:
    id: str
    text: str
    severity: Severity
    citation: str
    source_url: str
    predicate: Callable[[Action, DecisionContext, PolicyConfig], bool]


def _notice_of(action: Action) -> SendPreDebitNotice | None:
    if isinstance(action, ScheduleDebit):
        return action.notice
    if isinstance(action, SendPreDebitNotice):
        return action
    return None


@dataclass(frozen=True)
class _Contact:
    t: datetime
    channel: Channel
    template_id: str


def _contact_of(action: Action) -> _Contact | None:
    notice = _notice_of(action)
    if notice is not None:
        return _Contact(t=notice.t, channel=notice.channel, template_id=notice.template_id)
    if isinstance(action, OfferDateChange):
        return _Contact(t=action.t, channel=action.channel, template_id=action.template_id)
    return None


def _rbi_pdn_24h(action: Action, ctx: DecisionContext, config: PolicyConfig) -> bool:
    del ctx, config
    if isinstance(action, ScheduleDebit):
        return action.notice.t <= action.t - timedelta(hours=24)
    return True


def _rbi_pdn_optout(action: Action, ctx: DecisionContext, config: PolicyConfig) -> bool:
    del ctx, config
    notice = _notice_of(action)
    return notice.contained_optout_option if notice is not None else True


def _rbi_post_conf(action: Action, ctx: DecisionContext, config: PolicyConfig) -> bool:
    # Post-debit confirmation is an execution-time obligation on a *successful* debit,
    # which `decide()` proposes but never observes the outcome of — that belongs to the
    # execution layer (Phase 5), not a pre-decision predicate. Structurally true here.
    del action, ctx, config
    return True


def _rbi_afa_15k(action: Action, ctx: DecisionContext, config: PolicyConfig) -> bool:
    del config
    if not isinstance(action, ScheduleDebit):
        return True
    threshold = (
        AFA_THRESHOLD_INR_INSURANCE_MF_CC
        if ctx.merchant_category in AFA_HIGH_THRESHOLD_CATEGORIES
        else AFA_THRESHOLD_INR
    )
    if ctx.amount <= threshold:
        return True
    return action.afa_confirmed


def _rbi_no_charge(action: Action, ctx: DecisionContext, config: PolicyConfig) -> bool:
    # No `Action` in the closed set carries a customer-facing charge field — the e-mandate
    # facility fee this rule forbids is simply not representable. Structurally true.
    del action, ctx, config
    return True


def _conduct_hours(action: Action, ctx: DecisionContext, config: PolicyConfig) -> bool:
    del ctx, config
    contact = _contact_of(action)
    if contact is None:
        return True
    return CONTACT_HOUR_START <= contact.t.hour < CONTACT_HOUR_END


def _conduct_no_shame(action: Action, ctx: DecisionContext, config: PolicyConfig) -> bool:
    # No `Action` contacts anyone but the mandate's own customer, and message content is
    # always one of the fixed, pre-approved templates in `APPROVED_TEMPLATES` — there is
    # no free-text or third-party-contact path to shame anyone through. Structurally true.
    del action, ctx, config
    return True


def _conduct_record(action: Action, ctx: DecisionContext, config: PolicyConfig) -> bool:
    # Recording is `agent/audit.py`'s job, which runs outside this pure function (`decide()`
    # performs no I/O). The gate cannot itself write the record; it can only note that the
    # obligation exists, which every candidate does. Structurally true.
    del action, ctx, config
    return True


def _trai_dlt(action: Action, ctx: DecisionContext, config: PolicyConfig) -> bool:
    del ctx, config
    contact = _contact_of(action)
    if contact is None or contact.channel != Channel.SMS:
        return True
    return contact.template_id in APPROVED_TEMPLATES[Channel.SMS]


def _wa_utility(action: Action, ctx: DecisionContext, config: PolicyConfig) -> bool:
    del ctx, config
    contact = _contact_of(action)
    if contact is None or contact.channel != Channel.WHATSAPP:
        return True
    return contact.template_id in APPROVED_TEMPLATES[Channel.WHATSAPP]


def _dpdp_purpose(action: Action, ctx: DecisionContext, config: PolicyConfig) -> bool:
    # `decide()`'s signature only ever gives it one mandate's own `DecisionContext` — there
    # is no cross-mandate data even reachable from within a single call. Structurally true.
    del action, ctx, config
    return True


def _dpdp_minimise(action: Action, ctx: DecisionContext, config: PolicyConfig) -> bool:
    # Enforced once at import time (see module docstring) against `DecisionContext`'s own
    # field names; nothing left to check per call.
    del action, ctx, config
    return True


def _dobara_no_probe(action: Action, ctx: DecisionContext, config: PolicyConfig) -> bool:
    # `ScheduleDebit` has no amount field of its own — every debit it can represent is for
    # the mandate's own fixed `ctx.amount`, so a probing debit of a different amount is not
    # representable. Structurally true.
    del action, ctx, config
    return True


def _dobara_converge(action: Action, ctx: DecisionContext, config: PolicyConfig) -> bool:
    if not isinstance(action, OfferDateChange):
        return True
    if ctx.date_change_last_offered_cycle_index is None:
        return True
    min_gap = int(config.get("converge_min_cycles_between_date_changes"))
    return (ctx.cycle_index - ctx.date_change_last_offered_cycle_index) >= min_gap


def _dobara_fatigue(action: Action, ctx: DecisionContext, config: PolicyConfig) -> bool:
    if _contact_of(action) is None:
        return True
    cap = int(config.get("max_notifications_per_cycle"))
    return (ctx.notifications_sent_this_cycle + 1) <= cap


RULES: list[Rule] = [
    Rule(
        id="RBI-PDN-24H",
        text="Every debit attempt, including every retry, must be preceded by a "
        "pre-debit notification at least 24 hours earlier.",
        severity=Severity.HARD,
        citation="RBI e-mandate framework",
        source_url="https://rbi.org.in",
        predicate=_rbi_pdn_24h,
    ),
    Rule(
        id="RBI-PDN-OPTOUT",
        text="The pre-debit notification must carry an opt-out for this debit and for the mandate.",
        severity=Severity.HARD,
        citation="RBI e-mandate framework",
        source_url="https://rbi.org.in",
        predicate=_rbi_pdn_optout,
    ),
    Rule(
        id="RBI-POST-CONF",
        text="Every successful debit must be followed by a confirmation to the customer.",
        severity=Severity.HARD,
        citation="RBI e-mandate framework",
        source_url="https://rbi.org.in",
        predicate=_rbi_post_conf,
    ),
    Rule(
        id="RBI-AFA-15K",
        text="Debits above Rs.15,000 require Additional Factor Authentication "
        "(Rs.1,00,000 for insurance/mutual funds/credit-card bills).",
        severity=Severity.HARD,
        citation="RBI e-mandate framework",
        source_url="https://rbi.org.in",
        predicate=_rbi_afa_15k,
    ),
    Rule(
        id="RBI-NO-CHARGE",
        text="No charge may be levied on the customer for the e-mandate facility.",
        severity=Severity.HARD,
        citation="RBI e-mandate framework",
        source_url="https://rbi.org.in",
        predicate=_rbi_no_charge,
    ),
    Rule(
        id="CONDUCT-HOURS",
        text="No customer contact outside 08:00-19:00 IST.",
        severity=Severity.HARD,
        citation="RBI Fair Practices / Digital Lending",
        source_url="https://www.bajajfinserv.in/rbi-guidelines-for-recovery-agents",
        predicate=_conduct_hours,
    ),
    Rule(
        id="CONDUCT-NO-SHAME",
        text="No contact with third parties; no shaming; no coercive language.",
        severity=Severity.HARD,
        citation="RBI Digital Lending Guidelines",
        source_url="https://www.bajajfinserv.in/rbi-guidelines-for-recovery-agents",
        predicate=_conduct_no_shame,
    ),
    Rule(
        id="CONDUCT-RECORD",
        text="Every interaction digitally recorded.",
        severity=Severity.HARD,
        citation="RBI Fair Practices",
        source_url="https://www.bajajfinserv.in/rbi-guidelines-for-recovery-agents",
        predicate=_conduct_record,
    ),
    Rule(
        id="TRAI-DLT",
        text="Commercial SMS only via a registered DLT template; content must match the "
        "approved template.",
        severity=Severity.HARD,
        citation="TRAI TCCCPR",
        source_url="https://www.trai.gov.in",
        predicate=_trai_dlt,
    ),
    Rule(
        id="WA-UTILITY",
        text="WhatsApp messages must use an approved utility template within the allowed window.",
        severity=Severity.HARD,
        citation="WhatsApp Business Policy",
        source_url="https://business.whatsapp.com/policy",
        predicate=_wa_utility,
    ),
    Rule(
        id="DPDP-PURPOSE",
        text="Data used only for recovery of the mandate it was collected for.",
        severity=Severity.HARD,
        citation="DPDP Act 2023",
        source_url="https://www.meity.gov.in/data-protection-framework",
        predicate=_dpdp_purpose,
    ),
    Rule(
        id="DPDP-MINIMISE",
        text="No feature may encode individual balance or cash-flow inference.",
        severity=Severity.HARD,
        citation="DPDP Act 2023 s.6",
        source_url="https://www.meity.gov.in/data-protection-framework",
        predicate=_dpdp_minimise,
    ),
    Rule(
        id="DOBARA-NO-PROBE",
        text="No probing/test debits of an amount other than the scheduled one.",
        severity=Severity.HARD,
        citation="Self-imposed",
        source_url="docs/01-REGULATORY.md",
        predicate=_dobara_no_probe,
    ),
    Rule(
        id="DOBARA-CONVERGE",
        text="A mandate's debit date may be changed at most once per N cycles, and only "
        "toward a customer-declared or evidenced-stable date.",
        severity=Severity.SOFT,
        citation="Self-imposed",
        source_url="docs/01-REGULATORY.md",
        predicate=_dobara_converge,
    ),
    Rule(
        id="DOBARA-FATIGUE",
        text="Maximum notifications per mandate per cycle; hard cap regardless of expected value.",
        severity=Severity.HARD,
        citation="Self-imposed",
        source_url="docs/01-REGULATORY.md",
        predicate=_dobara_fatigue,
    ),
]


def evaluate(
    action: Action, ctx: DecisionContext, config: PolicyConfig
) -> tuple[list[Rule], list[Rule]]:
    """Returns `(satisfied, blocked)` — every rule the action was checked against,
    partitioned by whether its predicate passed."""
    satisfied: list[Rule] = []
    blocked: list[Rule] = []
    for rule in RULES:
        (satisfied if rule.predicate(action, ctx, config) else blocked).append(rule)
    return satisfied, blocked


def is_hard_compliant(action: Action, ctx: DecisionContext, config: PolicyConfig) -> bool:
    """The structural gate: `False` means this action must never be added to the
    candidate pool `agent/decide.py` scores. SOFT-rule violations do not disqualify."""
    return all(
        rule.predicate(action, ctx, config) for rule in RULES if rule.severity == Severity.HARD
    )
