"""A thin Razorpay **test-mode only** REST client, used exclusively by `api/main.py`'s
explicit proposal-execution endpoints — never by `agent/decide.py`, which never imports
this module or anything that could reach a network call
(`tests/test_no_llm_in_money_path.py`'s import-boundary discipline extends here too: the
money *decision* is `agent/`'s; this module only ever *proposes* it to Razorpay's test
rail, per docs/02-ARCHITECTURE.md "Actions execute as a **proposal**, never direct rail
calls").

**Credential-optional by design**, per docs/03-TECH-STACK.md's "no API key" requirement:
`RAZORPAY_KEY_ID`/`RAZORPAY_KEY_SECRET` unset (the committed `.env.example` default) means
`RazorpayClient.configured` is `False` and every write method raises `RazorpayNotConfigured`
— the app must never silently no-op or fake a response; the caller (an `api/main.py` route)
is expected to catch this and return a clear "not configured" response instead of a
fabricated success.

**What this client automates vs. what it doesn't, stated honestly rather than oversold:**
customer/plan/subscription creation and fetch, and webhook signature verification, are all
stable, well-documented Razorpay REST conventions this client implements directly. **Test-
mode outcome forcing (`success@razorpay` / `failure@razorpay`)** is a Checkout/payment-page
mechanism — the customer (or, in test mode, a scripted browser) enters that UPI VPA at the
hosted payment step, which happens client-side. There is no server-side "charge this
subscription right now and force this outcome" REST call this client fabricates; instead
`test_mode_vpa_for()` returns the correct VPA constant and `TEST_MODE_NOTE` documents this
limitation plainly, so the demo can construct a real Checkout session pointed at the right
VPA rather than a script pretending to trigger a charge Razorpay's API doesn't expose that
way.
"""

from __future__ import annotations

import hashlib
import hmac
import os
from typing import Any

import httpx

RAZORPAY_API_BASE = "https://api.razorpay.com/v1"

TEST_MODE_NOTE = (
    "Razorpay test-mode outcome forcing (success@razorpay / failure@razorpay) is a "
    "Checkout-step mechanism, not a server-side REST call -- this client exposes the VPA "
    "constants for constructing a real Checkout session, not a fabricated 'trigger charge' "
    "endpoint. See api/razorpay_client.py's module docstring."
)


class RazorpayNotConfigured(RuntimeError):
    """Raised by every write method when RAZORPAY_KEY_ID/RAZORPAY_KEY_SECRET are unset —
    never silently no-op, never a fabricated response."""


class RazorpayClient:
    def __init__(self, key_id: str | None = None, key_secret: str | None = None) -> None:
        self.key_id = key_id if key_id is not None else os.environ.get("RAZORPAY_KEY_ID", "")
        self.key_secret = (
            key_secret if key_secret is not None else os.environ.get("RAZORPAY_KEY_SECRET", "")
        )

    @property
    def configured(self) -> bool:
        # .env.example's committed placeholders (rzp_test_xxxxxxxxxxxx / a string of x's)
        # must count as "not configured", not as real credentials that happen to fail auth.
        return bool(self.key_id) and bool(self.key_secret) and "x" * 8 not in self.key_secret

    def _require_configured(self) -> None:
        if not self.configured:
            raise RazorpayNotConfigured(
                "RAZORPAY_KEY_ID/RAZORPAY_KEY_SECRET are not set (or are still the "
                ".env.example placeholders) -- see docs/03-TECH-STACK.md: the repo runs "
                "end-to-end without them, but Razorpay proposal-execution endpoints "
                "require real test-mode credentials."
            )

    def _client(self) -> httpx.Client:
        self._require_configured()
        return httpx.Client(
            base_url=RAZORPAY_API_BASE, auth=(self.key_id, self.key_secret), timeout=10.0
        )

    def create_customer(self, name: str, email: str, contact: str) -> dict[str, Any]:
        with self._client() as c:
            resp = c.post("/customers", json={"name": name, "email": email, "contact": contact})
            resp.raise_for_status()
            result: dict[str, Any] = resp.json()
            return result

    def create_plan(
        self, period: str, interval: int, item_name: str, amount_paise: int
    ) -> dict[str, Any]:
        """`period`: "daily" | "weekly" | "monthly" | "yearly". `amount_paise`: integer
        paise (Razorpay's REST API is paise-denominated everywhere, not rupees)."""
        with self._client() as c:
            resp = c.post(
                "/plans",
                json={
                    "period": period,
                    "interval": interval,
                    "item": {"name": item_name, "amount": amount_paise, "currency": "INR"},
                },
            )
            resp.raise_for_status()
            result: dict[str, Any] = resp.json()
            return result

    def create_subscription(
        self,
        plan_id: str,
        total_count: int,
        customer_notify: bool = True,
        customer_id: str | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "plan_id": plan_id,
            "total_count": total_count,
            "customer_notify": 1 if customer_notify else 0,
        }
        if customer_id is not None:
            payload["customer_id"] = customer_id
        with self._client() as c:
            resp = c.post("/subscriptions", json=payload)
            resp.raise_for_status()
            result: dict[str, Any] = resp.json()
            return result

    def fetch_subscription(self, subscription_id: str) -> dict[str, Any]:
        with self._client() as c:
            resp = c.get(f"/subscriptions/{subscription_id}")
            resp.raise_for_status()
            result: dict[str, Any] = resp.json()
            return result

    @staticmethod
    def verify_webhook_signature(payload_body: bytes, signature: str, webhook_secret: str) -> bool:
        """Razorpay's documented webhook verification: HMAC-SHA256 of the raw request
        body, hex-digested, compared to the `X-Razorpay-Signature` header — constant-time
        comparison (`hmac.compare_digest`), not `==`, so this check itself cannot leak
        timing information about the expected signature.
        """
        expected = hmac.new(
            webhook_secret.encode("utf-8"), payload_body, hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(expected, signature)


def test_mode_vpa_for(force_success: bool) -> str:
    return "success@razorpay" if force_success else "failure@razorpay"
