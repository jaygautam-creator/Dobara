"""Builds the Control Room's demo data: a small held-out population, run through the
already-tested `dobara` and `aggressive_8x` arms (`eval/runner.py::run_arm`) — never a
second, hand-rolled decision loop. `dobara`'s run also collects a real `AuditTrail`
(`eval/runner.py`'s `audit_trail` parameter, added 2026-08-26 for exactly this) so
`/audit`, `/queue`, and the SSE stream all serve genuine `agent.decide()` output, not a
mock.

**Deliberately not the 30-seed harness's population** (n=5,000/seed) — this is a small,
fast, UI-scale demo (`DEMO_N_CUSTOMERS`), computed once at process start and cached in
memory. `docs/03-TECH-STACK.md`'s "no API key" reproducibility requirement means this must
work with zero external calls; the demo world comes from `sim/`, never Razorpay's live
API (that integration is `api/razorpay_client.py`, used only for the explicit proposal-
execution endpoints, never to source the queue).

**Two data sources, same shape.** When `data/dobara.sqlite3` is present (a trained DB —
`make train` has run), the demo batch is built live, right now, from real `agent.decide()`
calls against the loaded models. When it is absent (the common case for anyone who has not
run the ~101-minute training/eval pipeline — including every fresh clone and the static
Vercel deploy), the exact same shape is loaded from the committed
`artifacts/demo_batch.json` fixture instead: real `agent.decide()` output, precomputed by
`make demo-fixture` against a trained DB and serialised once. This is no less real than the
live path for the same reason `api/main.py`'s SSE pacing note gives for streaming a
completed computation slowly: the decisions were genuinely made by `agent.decide()`, just
earlier. **The Control Room UI must label which source is live and say so plainly** — see
`/demo/meta`, which exists for exactly that footer.

Streaming is paced artificially (`api/main.py`'s SSE handler adds a small delay between
events) purely for the Control Room's "counters climbing" visual — the computation itself
is real and already complete by the time the process starts serving requests, in both
source modes; only the *delivery* is paced.
"""

from __future__ import annotations

import json
import threading
from dataclasses import dataclass
from pathlib import Path

from agent.audit import AuditRecord, AuditTrail
from agent.models import ModelBundle, load_model_bundle
from agent.policy import PolicyConfig, load_policy
from api import converters
from api.schemas import CounterOut, DecisionOut, QueueItemOut
from eval.arms import Arm
from eval.runner import MandateResult, run_arm
from eval.world import World, build_world
from models.ltv import LifeTable, build_life_table
from sim.params import Params, load_params

TRAIN_DB_PATH = "data/dobara.sqlite3"
DEMO_FIXTURE_PATH = Path("artifacts/demo_batch.json")
# Held out from both the seed=42 training population and the eval harness's seeds
# 101-130 -- a fresh demo-only world, small enough to compute and stream instantly.
DEMO_SEED = 9001
DEMO_N_CUSTOMERS = 150


@dataclass(frozen=True)
class DemoBatch:
    """Raw agent/eval objects from one live demo run -- only meaningful when
    `data/dobara.sqlite3` exists. `make demo-fixture` builds one of these and serialises
    its API-shaped view (`DemoData`, below) to `artifacts/demo_batch.json`."""

    world: World
    params: Params
    life_table: LifeTable
    model_bundle: ModelBundle
    dobara_results: list[MandateResult]
    aggressive_8x_results: list[MandateResult]
    audit_records: list[AuditRecord]


@dataclass(frozen=True)
class DemoData:
    """API-shaped demo output -- what every Control Room route actually serves,
    regardless of source. `source` is `"live"` when built from a fresh `DemoBatch` this
    process, `"fixture"` when loaded from the committed `artifacts/demo_batch.json`."""

    queue: list[QueueItemOut]
    counters: CounterOut
    audit_by_mandate: dict[int, list[DecisionOut]]
    approvals: list[DecisionOut]
    source: str  # "live" | "fixture"


_batch: DemoBatch | None = None
_data: DemoData | None = None
# RLock, not Lock: get_demo_data() can acquire this and then call get_demo_batch(),
# which acquires it again on the same thread -- a plain Lock would deadlock there.
_lock = threading.RLock()


def _build_demo_batch() -> DemoBatch:
    params = load_params()
    policy: PolicyConfig = load_policy()
    horizon_cycles = int(params.get("ltv.horizon_cycles"))
    model_bundle = load_model_bundle(TRAIN_DB_PATH)
    life_table = build_life_table(TRAIN_DB_PATH, horizon_cycles)
    world = build_world(params, seed=DEMO_SEED, n_customers=DEMO_N_CUSTOMERS)

    trail = AuditTrail()
    dobara_results = run_arm(
        world,
        Arm.DOBARA,
        params,
        life_table,
        policy=policy,
        model_bundle=model_bundle,
        holdout_fraction=0.0,
        audit_trail=trail,
    )
    aggressive_8x_results = run_arm(world, Arm.AGGRESSIVE_8X, params, life_table)

    return DemoBatch(
        world=world,
        params=params,
        life_table=life_table,
        model_bundle=model_bundle,
        dobara_results=dobara_results,
        aggressive_8x_results=aggressive_8x_results,
        audit_records=list(trail.records()),
    )


def get_demo_batch() -> DemoBatch:
    """Only valid when `data/dobara.sqlite3` is present. Builds (and caches) the live
    `DemoBatch` -- used by `make demo-fixture` and by `get_demo_data()`'s live path."""
    global _batch
    if _batch is not None:
        return _batch
    with _lock:
        if _batch is not None:  # another thread built it while we waited for the lock
            return _batch
        _batch = _build_demo_batch()
        return _batch


def demo_data_from_batch(batch: DemoBatch, source: str = "live") -> DemoData:
    """`DemoBatch` -> `DemoData`. Shared by the live path and `make demo-fixture`, which
    calls this once and serialises the result -- so the fixture is exactly what a live
    process would have computed, never a hand-shaped approximation of it."""
    queue = converters.queue_items(batch.audit_records, batch.world)
    counters = converters.compute_counters(batch.dobara_results, batch.aggressive_8x_results)
    audit_by_mandate: dict[int, list[DecisionOut]] = {}
    for record in batch.audit_records:
        audit_by_mandate.setdefault(record.ctx.mandate_id, []).append(
            converters.decision_out(record)
        )
    approvals = [
        converters.decision_out(r) for r in batch.audit_records if r.decision.requires_signoff
    ]
    return DemoData(
        queue=queue,
        counters=counters,
        audit_by_mandate=audit_by_mandate,
        approvals=approvals,
        source=source,
    )


def _demo_data_from_fixture() -> DemoData:
    raw = json.loads(DEMO_FIXTURE_PATH.read_text())
    return DemoData(
        queue=[QueueItemOut.model_validate(x) for x in raw["queue"]],
        counters=CounterOut.model_validate(raw["counters"]),
        audit_by_mandate={
            int(mandate_id): [DecisionOut.model_validate(d) for d in decisions]
            for mandate_id, decisions in raw["audit_by_mandate"].items()
        },
        approvals=[DecisionOut.model_validate(x) for x in raw["approvals"]],
        source="fixture",
    )


def get_demo_data() -> DemoData:
    """The single entry point every Control Room route should call. Live when
    `data/dobara.sqlite3` exists, the committed fixture otherwise -- see this module's
    docstring for why the fixture path is not a lesser stand-in."""
    global _data
    if _data is not None:
        return _data
    with _lock:
        if _data is not None:
            return _data
        if Path(TRAIN_DB_PATH).exists():
            _data = demo_data_from_batch(get_demo_batch(), source="live")
        elif DEMO_FIXTURE_PATH.exists():
            _data = _demo_data_from_fixture()
        else:
            raise FileNotFoundError(
                f"neither {TRAIN_DB_PATH} nor {DEMO_FIXTURE_PATH} exists -- run `make train` "
                "(for a live DB) or `make demo-fixture` (to regenerate the committed fixture "
                "from one) first."
            )
        return _data
