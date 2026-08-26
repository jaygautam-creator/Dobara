"""Builds the Control Room's demo batch: a small held-out population, run through the
already-tested `dobara` and `aggressive_8x` arms (`eval/runner.py::run_arm`) — never a
second, hand-rolled decision loop. `dobara`'s run also collects a real `AuditTrail`
(`eval/runner.py`'s new optional `audit_trail` parameter, added 2026-08-26 for exactly
this) so `/audit`, `/queue`, and the SSE stream all serve genuine `agent.decide()` output,
not a mock.

**Deliberately not the 30-seed harness's population** (n=5,000/seed) — this is a small,
fast, UI-scale demo (`DEMO_N_CUSTOMERS`), computed once at process start and cached in
memory. `docs/03-TECH-STACK.md`'s "no API key" reproducibility requirement means this must
work with zero external calls; the demo world comes from `sim/`, never Razorpay's live
API (that integration is `api/razorpay_client.py`, used only for the explicit proposal-
execution endpoints, never to source the queue).

Streaming is paced artificially (`api/main.py`'s SSE handler adds a small delay between
events) purely for the Control Room's "counters climbing" visual — the computation itself
is real and already complete by the time the process starts serving requests; only the
*delivery* is paced, stated here so that choice is never mistaken for the batch itself
running slowly.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass

from agent.audit import AuditRecord, AuditTrail
from agent.models import ModelBundle, load_model_bundle
from agent.policy import PolicyConfig, load_policy
from eval.arms import Arm
from eval.runner import MandateResult, run_arm
from eval.world import World, build_world
from models.ltv import LifeTable, build_life_table
from sim.params import Params, load_params

TRAIN_DB_PATH = "data/dobara.sqlite3"
# Held out from both the seed=42 training population and the eval harness's seeds
# 101-130 -- a fresh demo-only world, small enough to compute and stream instantly.
DEMO_SEED = 9001
DEMO_N_CUSTOMERS = 150


@dataclass(frozen=True)
class DemoBatch:
    world: World
    params: Params
    life_table: LifeTable
    model_bundle: ModelBundle
    dobara_results: list[MandateResult]
    aggressive_8x_results: list[MandateResult]
    audit_records: list[AuditRecord]


_batch: DemoBatch | None = None
_lock = threading.Lock()


def get_demo_batch() -> DemoBatch:
    """Lazy singleton — built on first request, not at import time (keeps `uvicorn
    --reload` and tests that only need a subset of `api/` fast to import), then cached
    for the life of the process.
    """
    global _batch
    if _batch is not None:
        return _batch
    with _lock:
        if _batch is not None:  # another thread built it while we waited for the lock
            return _batch
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

        _batch = DemoBatch(
            world=world,
            params=params,
            life_table=life_table,
            model_bundle=model_bundle,
            dobara_results=dobara_results,
            aggressive_8x_results=aggressive_8x_results,
            audit_records=list(trail.records()),
        )
        return _batch
