"""Guards against the audit_text class of bug: web/lib/types.ts is a hand-written
subset of api/schemas.py and can silently drift from what the committed artifacts
under artifacts/ actually contain (docs/DECISIONS.md [2026-08-28] "audit_text").
Asserts, directly against the real committed JSON, that fields the frontend reads are
actually present and non-empty -- not a schema-generation project, just the fields
found by grepping web/app and web/components for real field accesses.
"""

from __future__ import annotations

import json
from pathlib import Path

ARTIFACTS = Path(__file__).resolve().parent.parent / "artifacts"


def _load(name: str) -> dict:
    return json.loads((ARTIFACTS / name).read_text())


def _sample_decisions(demo_batch: dict, n: int = 50) -> list[dict]:
    decisions: list[dict] = []
    for trail in demo_batch["audit_by_mandate"].values():
        decisions.extend(trail)
        if len(decisions) >= n:
            break
    return decisions


def test_demo_batch_decision_fields_present_and_nonempty() -> None:
    demo_batch = _load("demo_batch.json")
    decisions = _sample_decisions(demo_batch)
    assert decisions, "expected at least one decision in demo_batch.json"

    # Fields DecisionCard / ControlRoomClient / renderAuditSections read unconditionally.
    always_present = [
        "mandate_id",
        "cycle_index",
        "attempt_index",
        "bank_id",
        "method",
        "amount",
        "now",
        "chosen",
        "expected_net",
        "confidence_band",
        "rupee_math",
        "requires_signoff",
        "notifications_sent_this_cycle",
        "consecutive_failed_cycles",
    ]
    for dec in decisions:
        for field in always_present:
            assert field in dec, f"decision missing key {field!r}"
            assert dec[field] not in (None, "", [], {}), (
                f"decision field {field!r} present but empty/null"
            )

    # audit_text must NOT be present -- scripts/build_demo_fixture.py deliberately
    # excludes it, and web/lib/types.ts's DecisionOut must not declare it either.
    for dec in decisions:
        assert "audit_text" not in dec

    types_ts = (Path(__file__).resolve().parent.parent / "web" / "lib" / "types.ts").read_text()
    assert "audit_text:" not in types_ts, (
        "DecisionOut must not declare audit_text -- it's never serialized "
        "(scripts/build_demo_fixture.py excludes it)"
    )


def test_home_demo_lanes_have_nonempty_events_and_totals() -> None:
    home_demo = _load("home_demo.json")
    for arm in ("aggressive_8x", "dobara"):
        lane = home_demo["lanes"][arm]
        assert lane["events"], f"{arm} lane has no events"
        totals = lane["totals"]
        for field in ("n_attempts", "n_notifications", "gross_recovered_inr", "net_ltv_inr"):
            assert field in totals


def test_compliance_rules_nonempty() -> None:
    rules = _load("compliance_rules.json")
    assert rules["rules"], "compliance_rules.json has no rules"
    for rule in rules["rules"]:
        assert rule["id"]
        assert rule["text"]
        assert rule["citation"]


def test_summary_json_headline_fields_present() -> None:
    summary = _load("summary.json")
    for arm in ("do_nothing", "razorpay_default", "aggressive_8x", "dobara", "oracle"):
        assert arm in summary["arms"]
    paired = summary["paired_dobara_vs_razorpay_default"]
    for field in ("mean_diff", "ci_lo", "ci_hi", "significant"):
        assert field in paired
