"""Smoke tests for `api/main.py`. Uses the real demo batch (`api/demo.py`'s cached
singleton) rather than mocking `agent.decide()` — the whole point of this API layer is
that it serves genuine model output, so a test suite that mocked the decision layer
would not actually verify the contract these tests exist to check.
"""

from __future__ import annotations

import hashlib
import hmac
import json

import pytest
from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)


def test_health() -> None:
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_evidence_summary_is_real_artifact_data() -> None:
    resp = client.get("/evidence/summary")
    assert resp.status_code == 200
    body = resp.json()
    paired = body["paired_dobara_vs_razorpay_default"]
    assert paired["arm_a"] == "dobara"
    assert paired["arm_b"] == "razorpay_default"
    assert isinstance(paired["mean_diff"], float)


def test_evidence_sensitivity_is_real_artifact_data() -> None:
    resp = client.get("/evidence/sensitivity")
    assert resp.status_code == 200
    body = resp.json()
    assert "break_even_vs_aggressive_8x" in body
    assert "break_even_vs_razorpay_default" in body
    assert "other_axes" in body


def test_queue_returns_live_decisions_ranked_by_amount() -> None:
    resp = client.get("/queue")
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) > 0
    amounts = [item["amount"] for item in items]
    assert amounts == sorted(amounts, reverse=True)
    # every mandate id appears exactly once -- one row per case, not per decision
    assert len({item["mandate_id"] for item in items}) == len(items)
    decision = items[0]["decision"]
    assert decision["chosen"]["action_type"] in {
        "schedule_debit",
        "offer_date_change",
        "stop",
        "abstain",
        "escalate_to_human",
    }
    assert "SAW" in decision["audit_text"]
    assert "WHY" in decision["audit_text"]


def test_counters_are_internally_consistent_with_queue() -> None:
    counters = client.get("/counters").json()
    queue = client.get("/queue").json()
    assert counters["n_mandates"] == len(queue)
    assert counters["net_ltv_inr"] != counters["comparison_aggressive_8x_net_ltv_inr"]


def test_audit_for_known_mandate_and_404_for_unknown() -> None:
    mandate_id = client.get("/queue").json()[0]["mandate_id"]
    resp = client.get(f"/audit/{mandate_id}")
    assert resp.status_code == 200
    records = resp.json()
    assert len(records) >= 1
    assert all(r["mandate_id"] == mandate_id for r in records)

    resp_404 = client.get("/audit/99999999")
    assert resp_404.status_code == 404


def test_approvals_only_contains_signoff_required_decisions() -> None:
    resp = client.get("/approvals")
    assert resp.status_code == 200
    for decision in resp.json():
        assert decision["requires_signoff"] is True


def test_batch_poll_matches_queue_and_counters() -> None:
    resp = client.get("/batch/poll")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["decisions"]) == len(client.get("/queue").json())
    assert body["counters"]["n_mandates"] == client.get("/counters").json()["n_mandates"]


def test_batch_stream_emits_decision_counters_done_in_order() -> None:
    with client.stream("GET", "/batch/stream") as resp:
        assert resp.status_code == 200
        event_types: list[str] = []
        for line in resp.iter_lines():
            if line.startswith("event: "):
                event_types.append(line.removeprefix("event: "))
    assert event_types[0] == "decision"
    assert event_types[-2] == "counters"
    assert event_types[-1] == "done"
    assert event_types.count("decision") == len(client.get("/queue").json())


def test_razorpay_status_unconfigured_by_default() -> None:
    resp = client.get("/razorpay/status")
    assert resp.status_code == 200
    body = resp.json()
    assert body["configured"] is False
    assert body["key_id_prefix"] is None


def test_razorpay_create_subscription_503s_when_unconfigured() -> None:
    resp = client.post("/razorpay/subscriptions", json={"plan_id": "plan_test", "total_count": 8})
    assert resp.status_code == 503


def test_razorpay_webhook_503s_when_secret_unconfigured() -> None:
    resp = client.post(
        "/razorpay/webhook",
        content=json.dumps({"event": "subscription.charged"}),
        headers={"X-Razorpay-Signature": "irrelevant", "Content-Type": "application/json"},
    )
    assert resp.status_code == 503


def test_razorpay_webhook_verifies_signature_when_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    secret = "a_real_test_webhook_secret"
    monkeypatch.setenv("RAZORPAY_WEBHOOK_SECRET", secret)
    body = json.dumps({"event": "subscription.charged"}).encode()
    good_sig = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()

    ok = client.post(
        "/razorpay/webhook",
        content=body,
        headers={"X-Razorpay-Signature": good_sig, "Content-Type": "application/json"},
    )
    assert ok.status_code == 200
    assert ok.json() == {"received": True, "event": "subscription.charged", "verified": True}

    bad = client.post(
        "/razorpay/webhook",
        content=body,
        headers={"X-Razorpay-Signature": "wrong", "Content-Type": "application/json"},
    )
    assert bad.status_code == 400
