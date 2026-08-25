"""The seven named stopping reasons. Every `STOP` action names exactly one, and it
appears in the audit trail and (eventually) the Control Room UI. See
docs/02-ARCHITECTURE.md "## The seven stopping reasons".
"""

from __future__ import annotations

from enum import Enum


class StoppingReason(Enum):
    HARD_DECLINE = "hard_decline"  # the decline reason is terminal; retrying cannot help
    MANDATE_REVOKED = "mandate_revoked"  # nothing left to recover against
    CUSTOMER_OPTED_OUT = "customer_opted_out"  # the customer used the control we gave them
    MAX_ATTEMPTS = "max_attempts"  # the configured cap for this cycle
    COST_CAP = "cost_cap"  # cumulative recovery spend exceeded its budget
    NEGATIVE_EXPECTED_VALUE = "negative_expected_value"  # the derived one — E[net] <= 0
    INSUFFICIENT_CONFIDENCE = "insufficient_confidence"  # the model abstained
