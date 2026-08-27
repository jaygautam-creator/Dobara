"""`make money-chart` -- builds `artifacts/money_chart_data.json`, the single-seed,
per-cycle cumulative money-over-time series behind `/evidence`'s headline chart
(`web/components/charts/MoneyChart.tsx`).

Per docs/DECISIONS.md [2026-08-27]: this artifact used to be produced by an uncommitted
scratch script, so it silently outlived the tie-break fix that the rest of the evidence
pipeline was reconciled against, and sat outside `check_artifact_freshness.py`'s
provenance gate. This script closes both gaps -- it is the one and only producer, and
`check_artifact_freshness.py` now watches it.

**Seed 301**, distinct from both the seed=42 training population (`sim.run`) and the
30-seed harness block (`eval.run.SEEDS`, 101-130) -- a genuinely held-out population,
matching the artifact's pre-existing `seed`/`n_customers` metadata exactly. Runs all 5
`eval.runner.run_arm` arms once each over that one population and sums each arm's
per-mandate `per_cycle_gross_inr` / `per_cycle_net_inr` (see `eval/runner.py::MandateResult`)
across mandates, cycle by cycle, to get the five cumulative series the chart plots.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from agent.models import load_model_bundle
from agent.policy import load_policy
from eval.arms import Arm
from eval.provenance import stamp
from eval.runner import run_arm
from eval.world import build_world
from models.ltv import build_life_table
from sim.params import load_params

TRAIN_DB_PATH = "data/dobara.sqlite3"
SEED = 301
OUT_PATH = Path("artifacts/money_chart_data.json")


def main() -> None:
    params = load_params()
    policy = load_policy()
    n_customers = int(params.get("population.n_customers"))
    n_merchants = int(params.get("population.n_merchants"))
    n_cycles = int(params.get("population.n_cycles"))
    horizon_cycles = int(params.get("ltv.horizon_cycles"))
    holdout_fraction = float(policy.get("holdout_fraction"))

    model_bundle = load_model_bundle(TRAIN_DB_PATH)
    life_table = build_life_table(TRAIN_DB_PATH, horizon_cycles)

    world = build_world(params, seed=SEED, n_customers=n_customers, n_merchants=n_merchants)

    payload: dict[str, object] = {
        "seed": SEED,
        "n_customers": n_customers,
        "cycle_index": list(range(1, n_cycles + 1)),
    }

    for arm in Arm:
        kwargs: dict[str, Any] = {}
        if arm is Arm.DOBARA:
            kwargs = {
                "policy": policy,
                "model_bundle": model_bundle,
                "holdout_fraction": holdout_fraction,
            }
        results = run_arm(world, arm, params, life_table, **kwargs)
        gross = [0.0] * n_cycles
        net = [0.0] * n_cycles
        for r in results:
            for i in range(n_cycles):
                gross[i] += r.per_cycle_gross_inr[i]
                net[i] += r.per_cycle_net_inr[i]
        payload[arm.value] = {"gross": gross, "net": net}

    payload["provenance"] = stamp()

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(payload, indent=2))
    print(f"wrote {OUT_PATH} ({OUT_PATH.stat().st_size / 1024:.1f} KB)")


if __name__ == "__main__":
    main()
