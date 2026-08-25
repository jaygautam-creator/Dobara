"""Characterization test for the `agent/decide.py` batching refactor (docs/DECISIONS.md
[2026-08-25] "agent/decide.py batched scoring"). Snapshots the full `Decision` output for
~20 varied `DecisionContext`s to `tests/fixtures/decide_characterization.json` and asserts
byte-for-byte (post float-rounding) equality on every run.

Unlike `tests/test_agent_decide.py`'s fakes (constant `p_success`/`p_revoke` regardless of
row content), the fakes here vary `p_success` and the feature-attribution contribution by
`day_of_month` — a constant-output fake cannot catch a batching bug that scrambles which
prediction row maps back to which candidate, since every candidate would score identically
either way. This one can: if a future refactor mis-orders the batched
`predict_lgbm`/`predict_lgbm_contrib` results relative to the candidate list, a candidate
will pick up a *different* day's prediction and `expected_net`/`chosen`/`feature_attribution`
will (almost certainly) change for at least one of the 20 cases below.

To regenerate the fixture deliberately (only after a reviewed, intentional behavior
change — never to silence a failing assertion):
    uv run python -c \
        "from tests.test_agent_decide_characterization import write_fixture; write_fixture()"
"""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from agent.actions import Abstain, EscalateToHuman, OfferDateChange, ScheduleDebit, Stop
from agent.context import Decision, DecisionContext
from agent.decide import decide
from agent.models import ModelBundle
from features.recovery import RECOVERY_FEATURE_COLUMNS
from models.ltv import LifeTable
from sim.params import Params
from tests.test_agent_decide import _bank_health, _base_ctx, _policy_config, _sim_params

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "decide_characterization.json"


class _VaryingRecoveryModel:
    model_version = "fake_recovery_varying_v1"

    def predict_lgbm(self, df: pd.DataFrame) -> list[float]:
        return [0.3 + 0.01 * (int(row["day_of_month"]) % 20) for _, row in df.iterrows()]

    def predict_lgbm_contrib(self, df: pd.DataFrame) -> list[list[float]]:
        return [
            [0.001 * (i + int(row["day_of_month"])) for i in range(len(RECOVERY_FEATURE_COLUMNS))]
            + [0.05]
            for _, row in df.iterrows()
        ]


class _VaryingHazardModel:
    model_version = "fake_hazard_varying_v1"

    def predict(self, df: pd.DataFrame) -> list[float]:
        return [0.02 + 0.0003 * len(str(row["method"])) for _, row in df.iterrows()]


def _life_table() -> LifeTable:
    survival = {
        (cat, age): max(0.0, 1.0 - 0.04 * age) for cat in ("ott", "sip") for age in range(9)
    }
    return LifeTable(survival=survival, horizon_cycles=8)


def _bundle(
    slice_n: int = 500, slice_brier: float = 0.12, changepoint: bool = False
) -> ModelBundle:
    slice_block = {"n": slice_n, "brier_score": {"point": slice_brier}}
    return ModelBundle(
        recovery=_VaryingRecoveryModel(),  # type: ignore[arg-type]
        hazard=_VaryingHazardModel(),  # type: ignore[arg-type]
        life_table=_life_table(),
        sim_params=_sim_params(),
        recovery_slices_by_bank={"HDFC": slice_block, "SBI": slice_block, "ICICI": slice_block},
        hazard_slices_by_method={"upi_autopay": slice_block, "card": slice_block},
        bank_health=_bank_health(changepoint),
    )


def _cases() -> list[tuple[str, DecisionContext, ModelBundle, Params]]:
    """~20 varied cases spanning bank, method, attempt_index, amount, declared-preferred-day,
    near-fatigue-cap, near-cost-cap, and each abstention trigger.
    """
    cases: list[tuple[str, DecisionContext, ModelBundle, Params]] = []

    cases.append(("baseline", _base_ctx(), _bundle(), _policy_config()))
    cases.append(("bank_sbi", _base_ctx(bank_id="SBI"), _bundle(), _policy_config()))
    cases.append(("method_card", _base_ctx(method="card"), _bundle(), _policy_config()))
    cases.append(("attempt_index_1", _base_ctx(attempt_index=1), _bundle(), _policy_config()))
    cases.append(("small_amount", _base_ctx(amount=99.0), _bundle(), _policy_config()))
    cases.append(
        (
            "large_amount_afa",
            _base_ctx(amount=25000.0, afa_threshold_applicable=True),
            _bundle(),
            _policy_config(),
        )
    )
    cases.append(
        (
            "declared_day",
            _base_ctx(has_declared_preferred_day=True, declared_preferred_day=12),
            _bundle(),
            _policy_config(),
        )
    )
    cases.append(
        (
            "declared_day_recent_offer",
            _base_ctx(
                has_declared_preferred_day=True,
                declared_preferred_day=12,
                date_change_last_offered_cycle_index=6,
                cycle_index=7,
            ),
            _bundle(),
            _policy_config(converge_min_cycles_between_date_changes=4),
        )
    )
    cases.append(
        (
            "near_max_attempts",
            _base_ctx(attempt_index=3),
            _bundle(),
            _policy_config(max_attempts_per_cycle=3),
        )
    )
    cases.append(
        (
            "at_max_attempts",
            _base_ctx(attempt_index=4),
            _bundle(),
            _policy_config(max_attempts_per_cycle=3),
        )
    )
    cases.append(
        (
            "near_cost_cap",
            _base_ctx(notification_cost_spent_this_cycle_inr=4.9),
            _bundle(),
            _policy_config(cost_cap_inr=5.0),
        )
    )
    cases.append(
        (
            "at_cost_cap",
            _base_ctx(notification_cost_spent_this_cycle_inr=5.0),
            _bundle(),
            _policy_config(cost_cap_inr=5.0),
        )
    )
    cases.append(
        (
            "hard_decline",
            _base_ctx(last_attempt_outcome="hard_decline"),
            _bundle(),
            _policy_config(),
        )
    )
    cases.append(("mandate_revoked", _base_ctx(mandate_revoked=True), _bundle(), _policy_config()))
    cases.append(
        ("customer_opted_out", _base_ctx(customer_opted_out=True), _bundle(), _policy_config())
    )
    cases.append(
        (
            "abstain_insufficient_slice_n",
            _base_ctx(),
            _bundle(slice_n=5),
            _policy_config(min_slice_n=30),
        )
    )
    cases.append(
        (
            "abstain_changepoint",
            _base_ctx(),
            _bundle(slice_n=5000, changepoint=True),
            _policy_config(),
        )
    )
    cases.append(
        (
            "abstain_slice_calibration_error",
            _base_ctx(),
            _bundle(slice_n=5000, slice_brier=0.3),
            _policy_config(max_slice_brier=0.15),
        )
    )
    cases.append(
        (
            "abstain_ci_straddles_zero",
            _base_ctx(),
            _bundle(slice_n=30, slice_brier=0.1),
            _policy_config(min_slice_n=30, max_slice_brier=0.5),
        )
    )
    cases.append(
        (
            "late_cycle_window",
            _base_ctx(now=datetime(2026, 8, 30, 9, 0, 0), cycle_end=datetime(2026, 9, 2)),
            _bundle(),
            _policy_config(),
        )
    )
    cases.append(
        (
            "cold_start_early_attempt",
            _base_ctx(cycle_index=1, attempt_index=1, n_attempts_to_date=0, n_successes_to_date=0),
            _bundle(),
            _policy_config(),
        )
    )
    return cases


def _action_to_json(action: Any) -> dict[str, Any]:
    if isinstance(action, ScheduleDebit):
        return {
            "type": "ScheduleDebit",
            "t": action.t.isoformat(),
            "afa_confirmed": action.afa_confirmed,
            "notice_t": action.notice.t.isoformat(),
            "notice_channel": action.notice.channel.value,
            "notice_template_id": action.notice.template_id,
        }
    if isinstance(action, OfferDateChange):
        return {
            "type": "OfferDateChange",
            "t": action.t.isoformat(),
            "channel": action.channel.value,
            "template_id": action.template_id,
            "new_preferred_day": action.new_preferred_day,
        }
    if isinstance(action, Stop):
        return {"type": "Stop", "reason": action.reason.value}
    if isinstance(action, Abstain):
        return {"type": "Abstain", "reason": action.reason.value}
    if isinstance(action, EscalateToHuman):
        return {"type": "EscalateToHuman", "reason": action.reason}
    raise TypeError(type(action).__name__)  # pragma: no cover


def _round(x: float) -> float:
    return round(float(x), 6)


def _decision_to_json(d: Decision) -> dict[str, Any]:
    return {
        "chosen": _action_to_json(d.chosen),
        "expected_net": _round(d.expected_net),
        "confidence_band": [_round(d.confidence_band[0]), _round(d.confidence_band[1])],
        "rejected_alternatives": [
            {
                "description": a.description,
                "expected_net": _round(a.expected_net),
                "reason": a.reason,
            }
            for a in d.rejected_alternatives
        ],
        "clauses_satisfied": [{"id": c.id, "citation": c.citation} for c in d.clauses_satisfied],
        "clauses_blocked": [{"id": c.id, "citation": c.citation} for c in d.clauses_blocked],
        "rupee_math": {k: _round(v) for k, v in asdict(d.rupee_math).items()},
        "model_versions": d.model_versions,
        "feature_attribution": {k: _round(v) for k, v in d.feature_attribution.items()},
        "stopping_reason": d.stopping_reason.value if d.stopping_reason else None,
        "requires_signoff": d.requires_signoff,
    }


def _run_all_cases() -> dict[str, Any]:
    return {
        name: _decision_to_json(decide(ctx, models, config))
        for name, ctx, models, config in _cases()
    }


def write_fixture() -> None:
    FIXTURE_PATH.parent.mkdir(parents=True, exist_ok=True)
    FIXTURE_PATH.write_text(json.dumps(_run_all_cases(), indent=2, sort_keys=True) + "\n")


def test_decide_output_matches_characterization_fixture() -> None:
    actual = _run_all_cases()
    expected = json.loads(FIXTURE_PATH.read_text())
    assert actual == expected, (
        "agent/decide.py's output diverged from tests/fixtures/decide_characterization.json. "
        "If this is an intentional, reviewed behavior change, regenerate deliberately via "
        "write_fixture() and explain why in docs/DECISIONS.md — never to silence this check."
    )
