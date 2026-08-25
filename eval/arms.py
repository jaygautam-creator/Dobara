"""The five arms, per `docs/07-EVAL-SPEC.md`'s arm table. `Arm` names them; the
attempt-cadence parameters for the two non-live arms live here (`razorpay_default` reuses
`sim/params.yaml`'s existing `retry_policy.*` — the same values that generated the Phase
1/2 training data — so the arm can't silently drift from what it claims to replicate;
`aggressive_8x` gets its own declared block, `sim/params.yaml`'s `eval.*`, since those
numbers don't exist anywhere else). `dobara` calls `agent.decide()` live; `oracle` peeks
at latent balance instead of following a fixed cadence (see
`eval/runner.py::_run_oracle_arm`).

**`do_nothing` is the floor: ZERO attempts, ZERO notifications, ZERO gross recovered.**
Per docs/07-EVAL-SPEC.md's arm table: "No recovery attempted. The floor. Establishes what
is at stake." `max_attempts=0` below is the whole implementation — the mandate's cycles
elapse with no debit ever tried. This was previously `max_attempts=1` (read as "the
original scheduled debit still happens, only retries are skipped"), which is wrong: it
made `do_nothing` recover almost everything (nearly identical to every retrying arm) and
sent tens of thousands of notifications — the opposite of "no recovery attempted." Fixed
2026-08-25 after the bug was caught in review; see docs/DECISIONS.md.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from sim.params import Params


class Arm(StrEnum):
    DO_NOTHING = "do_nothing"
    RAZORPAY_DEFAULT = "razorpay_default"
    AGGRESSIVE_8X = "aggressive_8x"
    DOBARA = "dobara"
    ORACLE = "oracle"


@dataclass(frozen=True)
class Cadence:
    max_attempts: int
    min_gap_hours: int
    offers_date_change: bool  # only razorpay_default replicates sim.engine's date-change mechanic
    # `notification.fatigue_cap_per_cycle` (sim/params.yaml) is DOBARA-FATIGUE — a
    # self-imposed restraint (docs/01-REGULATORY.md: source "Self-imposed"), not a real
    # regulatory ceiling razorpay_default or the Western dunning playbook would observe.
    # `sim.engine.run_simulation` already bakes it into the razorpay_default-equivalent
    # generator (Phase 1, unchanged here — bug-for-bug replicated). aggressive_8x must
    # NOT respect it, or its whole distinguishing behaviour (up to 8 retries) can never
    # fire once the same 3-notification cap binds first, which defeats its purpose as
    # the mechanism-demonstration arm. See docs/DECISIONS.md [2026-08-25]
    # "aggressive_8x must not respect DOBARA-FATIGUE".
    respects_fatigue_cap: bool


def razorpay_default_cadence(params: Params) -> Cadence:
    return Cadence(
        max_attempts=int(params.get("retry_policy.max_attempts_default_policy")),
        min_gap_hours=int(params.get("retry_policy.min_gap_hours_between_attempts")),
        offers_date_change=True,
        respects_fatigue_cap=True,
    )


def aggressive_8x_cadence(params: Params) -> Cadence:
    return Cadence(
        max_attempts=int(params.get("eval.aggressive_8x_max_attempts")),
        min_gap_hours=int(params.get("eval.aggressive_8x_min_gap_hours_between_attempts")),
        offers_date_change=False,
        respects_fatigue_cap=False,
    )


DO_NOTHING_CADENCE = Cadence(
    max_attempts=0, min_gap_hours=24, offers_date_change=False, respects_fatigue_cap=True
)
