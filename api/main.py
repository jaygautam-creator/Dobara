"""The Control Room + evidence API, per docs/02-ARCHITECTURE.md "`api/` — FastAPI":
"Thin. Serves the queue, streams a live batch run over SSE, exposes audit records,
proxies Razorpay test-mode calls. No business logic — it calls `agent/`."

Run with `make api` (`uvicorn api.main:app --reload --port 8000`). Every figure this API
serves is either read live from `agent.decide()` (via `api/demo.py`'s cached demo batch)
or read verbatim from `artifacts/summary.json` / `artifacts/sensitivity.json` — never
hand-typed, matching `eval/run.py`'s own discipline.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from api.demo import get_demo_data
from api.razorpay_client import (
    TEST_MODE_NOTE,
    RazorpayClient,
    RazorpayNotConfigured,
    test_mode_vpa_for,
)
from api.schemas import (
    CounterOut,
    DecisionOut,
    QueueItemOut,
    RazorpaySubscriptionOut,
    RazorpayWebhookAckOut,
)

ARTIFACTS_DIR = Path("artifacts")

app = FastAPI(
    title="Dobara API",
    description=(
        "AI revenue-recovery agent for Indian recurring payments — Control Room + evidence API."
    ),
    version="0.1.0",
)

# Permissive for local dev / the deployed Next.js frontend on a different origin (Vercel
# preview URLs vary) -- this API serves no cookies/session auth, every route is either
# read-only public evidence or a test-mode-only proposal endpoint, so a wide CORS policy
# has no meaningful blast radius here.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


def _read_artifact_json(name: str) -> dict[str, Any]:
    path = ARTIFACTS_DIR / name
    if not path.exists():
        raise HTTPException(
            status_code=503,
            detail=f"{path} not found — run `make eval` (or `make demo`) to generate it first.",
        )
    result: dict[str, Any] = json.loads(path.read_text())
    return result


@app.get("/evidence/summary")
def evidence_summary() -> dict[str, Any]:
    """`artifacts/summary.json` verbatim — five arms, paired comparisons, robustness
    slices, per docs/07-EVAL-SPEC.md. The `/evidence` page's entire data source."""
    return _read_artifact_json("summary.json")


@app.get("/evidence/sensitivity")
def evidence_sensitivity() -> dict[str, Any]:
    """`artifacts/sensitivity.json` verbatim — the hazard sweep, both break-evens (incl.
    the NPCI-ratio-strengthened one), and the three other declared axes."""
    return _read_artifact_json("sensitivity.json")


@app.get("/demo/meta")
def demo_meta() -> dict[str, Any]:
    """Which data source `/queue`, `/counters`, `/audit`, `/approvals`, and `/batch/*`
    are currently serving -- `"live"` (real `agent.decide()` calls made by this running
    process, `data/dobara.sqlite3` present) or `"fixture"` (the committed
    `artifacts/demo_batch.json`, real `agent.decide()` output precomputed by
    `make demo-fixture` against a trained DB). The Control Room UI footer must render
    this label plainly, per PROGRESS.md's data-shipping decision -- see `api/demo.py`'s
    module docstring for why the fixture path is not a lesser stand-in."""
    data = get_demo_data()
    return {
        "source": data.source,
        "note": (
            "Live: agent.decide() run just now by this API process."
            if data.source == "live"
            else "Precomputed: real agent.decide() output, serialised by `make demo-fixture` "
            "against a trained DB. Run `make api` with `data/dobara.sqlite3` present to "
            "regenerate live."
        ),
    }


@app.get("/queue", response_model=list[QueueItemOut])
def queue() -> list[QueueItemOut]:
    """The Control Room's case queue: one row per demo mandate (its first live decision),
    ranked by ₹ at risk descending, per docs/08-FRONTEND-SPEC.md."""
    return get_demo_data().queue


@app.get("/counters", response_model=CounterOut)
def counters() -> CounterOut:
    """Header-tile numbers for the Control Room, plus the `aggressive_8x` comparison
    figures the comparison toggle needs — computed once from the cached demo data, not
    from the client's own streamed-event bookkeeping (so a client that misses SSE events
    still gets a correct final total via `/counters` or `/batch/poll`)."""
    return get_demo_data().counters


@app.get("/audit/{mandate_id}", response_model=list[DecisionOut])
def audit_for_mandate(mandate_id: int) -> list[DecisionOut]:
    """Every live decision made for one mandate, in order — `/audit/[decision_id]`'s data
    source (docs/08-FRONTEND-SPEC.md). `decision_id` here is the mandate id plus its
    position in this list; there's no separate decision-id namespace, one mandate's
    decisions are already totally ordered by `(cycle_index, attempt_index)`."""
    records = get_demo_data().audit_by_mandate.get(mandate_id)
    if not records:
        raise HTTPException(status_code=404, detail=f"no decisions found for mandate {mandate_id}")
    return records


@app.get("/approvals", response_model=list[DecisionOut])
def approvals() -> list[DecisionOut]:
    """Decisions above the human sign-off threshold (`Decision.requires_signoff`) —
    docs/08-FRONTEND-SPEC.md's "Approval queue"."""
    return get_demo_data().approvals


# --- SSE streaming + polling fallback, per docs/08-FRONTEND-SPEC.md "SSE for the live
# run, with polling fallback" and PROGRESS.md's Phase 5 checklist. ---

_STREAM_DELAY_SECONDS = 0.08  # paced for the Control Room's visual effect; see api/demo.py


def _sse_event(event_type: str, payload: BaseModel | dict[str, Any]) -> str:
    data = payload.model_dump_json() if isinstance(payload, BaseModel) else json.dumps(payload)
    return f"event: {event_type}\ndata: {data}\n\n"


@app.get("/batch/stream")
async def batch_stream(request: Request) -> StreamingResponse:
    """Streams the case queue as `decision` events, then a final `counters` event, then
    `done` — the computation is already complete (`api/demo.py`'s cached batch), only the
    delivery is paced, for the Control Room's "counters climbing" effect. A client that
    disconnects mid-stream (checked via `request.is_disconnected()`) stops the generator
    early rather than continuing to compute events nobody will see.
    """
    data = get_demo_data()
    items = data.queue
    counter_snapshot = data.counters

    async def event_source() -> AsyncIterator[str]:
        for item in items:
            if await request.is_disconnected():
                return
            yield _sse_event("decision", item)
            await asyncio.sleep(_STREAM_DELAY_SECONDS)
        yield _sse_event("counters", counter_snapshot)
        yield _sse_event("done", {"n_mandates": len(items)})

    return StreamingResponse(event_source(), media_type="text/event-stream")


@app.get("/batch/poll")
def batch_poll() -> dict[str, Any]:
    """Polling fallback for clients that can't hold an SSE connection open — returns the
    same data `/batch/stream` would eventually deliver, all at once."""
    data = get_demo_data()
    return {
        "decisions": [item.model_dump(mode="json") for item in data.queue],
        "counters": data.counters.model_dump(mode="json"),
    }


# --- Razorpay test-mode proposal endpoints. Never called by agent/decide.py; the money
# decision has already been made by the time any of these run. ---


@app.get("/razorpay/status")
def razorpay_status() -> dict[str, Any]:
    client = RazorpayClient()
    return {
        "configured": client.configured,
        "key_id_prefix": client.key_id[:12] if client.configured else None,
        "note": TEST_MODE_NOTE,
    }


class CreateSubscriptionRequest(BaseModel):
    plan_id: str
    total_count: int
    customer_notify: bool = True
    customer_id: str | None = None
    force_outcome: str | None = None  # "success" | "failure" | None


@app.post("/razorpay/subscriptions", response_model=RazorpaySubscriptionOut)
def create_subscription(req: CreateSubscriptionRequest) -> RazorpaySubscriptionOut:
    """Proposes (creates) a real Razorpay test-mode subscription — this is the one place
    in the whole system an `agent/decide.py` decision, once chosen, becomes a real
    (test-mode) rail call. `force_outcome`, if given, is echoed back as the VPA the demo
    Checkout session should use (`test_mode_vpa_for`) — it does not itself force anything
    server-side; see `api/razorpay_client.py`'s module docstring for why.
    """
    client = RazorpayClient()
    try:
        raw = client.create_subscription(
            plan_id=req.plan_id,
            total_count=req.total_count,
            customer_notify=req.customer_notify,
            customer_id=req.customer_id,
        )
    except RazorpayNotConfigured as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    if req.force_outcome is not None:
        raw["_dobara_demo_test_mode_vpa"] = test_mode_vpa_for(req.force_outcome == "success")
    return RazorpaySubscriptionOut(
        id=raw["id"],
        status=raw["status"],
        plan_id=raw["plan_id"],
        customer_notify=bool(raw.get("customer_notify")),
        short_url=raw.get("short_url"),
        raw=raw,
    )


@app.post("/razorpay/webhook", response_model=RazorpayWebhookAckOut)
async def razorpay_webhook(request: Request) -> RazorpayWebhookAckOut:
    """Receives a Razorpay test-mode webhook, verifies its signature against
    `RAZORPAY_WEBHOOK_SECRET`, and acknowledges it. Per docs/02-ARCHITECTURE.md, this is
    an intake point only — it never re-triggers `agent/decide.py` on its own; a real
    integration would enqueue the event for the next scheduled decision pass.
    """
    import os

    body = await request.body()
    signature = request.headers.get("X-Razorpay-Signature", "")
    webhook_secret = os.environ.get("RAZORPAY_WEBHOOK_SECRET", "")
    if not webhook_secret or "x" * 8 in webhook_secret:
        raise HTTPException(
            status_code=503,
            detail=(
                "RAZORPAY_WEBHOOK_SECRET is not configured (or is the .env.example placeholder)."
            ),
        )
    verified = RazorpayClient.verify_webhook_signature(body, signature, webhook_secret)
    if not verified:
        raise HTTPException(status_code=400, detail="webhook signature verification failed")
    payload = json.loads(body)
    return RazorpayWebhookAckOut(received=True, event=payload.get("event"), verified=True)
