"""`make home-demo` -- builds `artifacts/home_demo.json`, the per-beat reconstruction of
**one real mandate under two arms** behind the landing page's side-by-side demonstration
(`docs/10-REDESIGN.md` §4 `/` beat 2, "the highest-value single element on the site").

The page shows the `aggressive_8x` lane firing one legally-mandatory pre-debit
notification per retry until the customer revokes the mandate, against the `dobara` lane
stopping early and keeping it alive. Every number and every beat on that page comes from
this artifact: the same `eval.runner.run_arm` the evidence pipeline uses, over the same
held-out **seed 301** population `scripts/build_money_chart.py` aggregates for
`/evidence`'s money chart -- so the mandate on the landing page is literally one row of
the population behind the headline chart, not a separate hand-authored story. Nothing
here is authored, ordered or rounded by hand; `run_arm(..., trace=True)` records the
beats (`eval/runner.py::AttemptEvent`) as they actually happen.

**Selection is mechanical, median-not-maximal, and recorded.** Among mandates that
revoked under `aggressive_8x` but survived under `dobara`, this picks the **median** case
by dobara's net-LTV advantage on that mandate -- deliberately not the best one. Picking
the maximum would make the landing page's one worked example an outlier chosen because it
flatters the thesis; the median of a stated population is a claim a reader can check, and
`selection` carries the population's size and the p25/median/p75 of that advantage so the
spread around the shown case is visible rather than hidden. (An earlier version of this
script ranked by notifications-before-revocation and selected a mandate that revoked in
the *final* cycle, where almost no lifetime value remains to forgo -- a case in which the
aggressive lane nets more. Real, and exactly the wrong number to build a headline on; see
`docs/DECISIONS.md` [2026-08-28].)

Run after `make train` (needs `data/dobara.sqlite3`). Re-run whenever the world seed, the
trained models, or the arms change -- `scripts/check_artifact_freshness.py` enforces it.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from agent.models import load_model_bundle
from agent.policy import load_policy
from eval.arms import Arm
from eval.provenance import stamp
from eval.runner import MandateResult, run_arm
from eval.world import build_world
from models.ltv import build_life_table
from sim.params import load_params

TRAIN_DB_PATH = "data/dobara.sqlite3"
SEED = 301  # the held-out demo population, identical to scripts/build_money_chart.py
OUT_PATH = Path("artifacts/home_demo.json")

SELECTION_CRITERIA = (
    "revoked under aggressive_8x and not under dobara; the median case by dobara's "
    "net-LTV advantage over aggressive_8x on that mandate (ties broken by mandate_id)"
)


def _lane(res: MandateResult) -> dict[str, Any]:
    """One arm's view of the mandate: the beats, plus the totals the page's counters read.
    Every field is copied off `MandateResult` -- the same object the evaluation scores."""
    return {
        "events": [asdict(e) for e in res.events],
        "totals": {
            "n_attempts": res.n_attempts,
            "n_notifications": res.n_notifications,
            "n_successes": res.n_successes,
            "gross_recovered_inr": res.gross_recovered_inr,
            "notification_cost_inr": res.notification_cost_inr,
            "revoked": res.revoked,
            "revoked_at_cycle": res.revoked_at_cycle,
            "ltv_lost_inr": res.ltv_lost_inr,
            "net_ltv_inr": res.net_ltv_inr,
        },
    }


def _quantile(sorted_values: list[float], q: float) -> float:
    """Nearest-rank quantile over an already-sorted list -- no interpolation, so every
    number reported is a value some real mandate actually had."""
    if not sorted_values:
        raise ValueError("empty")
    index = min(len(sorted_values) - 1, max(0, round(q * (len(sorted_values) - 1))))
    return sorted_values[index]


def main() -> None:
    params = load_params()
    policy = load_policy()
    n_customers = int(params.get("population.n_customers"))
    n_merchants = int(params.get("population.n_merchants"))
    horizon_cycles = int(params.get("ltv.horizon_cycles"))

    model_bundle = load_model_bundle(TRAIN_DB_PATH)
    life_table = build_life_table(TRAIN_DB_PATH, horizon_cycles)
    world = build_world(params, seed=SEED, n_customers=n_customers, n_merchants=n_merchants)

    aggressive = {
        r.mandate_id: r for r in run_arm(world, Arm.AGGRESSIVE_8X, params, life_table, trace=True)
    }
    dobara = {
        r.mandate_id: r
        for r in run_arm(
            world,
            Arm.DOBARA,
            params,
            life_table,
            policy=policy,
            model_bundle=model_bundle,
            # The landing page compares two *policies* on one mandate. A mandate routed to
            # dobara's permanent holdout slice would be running razorpay_default's cadence
            # under a "dobara" label, which is not what the page claims to show -- so the
            # holdout is switched off here. It stays on everywhere it reports a number
            # (eval/run.py), which is where it exists to protect against optimism.
            holdout_fraction=0.0,
            trace=True,
        )
    }

    candidates = [
        mandate_id
        for mandate_id, agg in aggressive.items()
        if agg.revoked and not dobara[mandate_id].revoked
    ]
    if not candidates:
        raise SystemExit(f"no mandate in seed {SEED} revoked under aggressive_8x but not dobara")

    def advantage(mandate_id: int) -> float:
        return dobara[mandate_id].net_ltv_inr - aggressive[mandate_id].net_ltv_inr

    ranked = sorted(candidates, key=lambda mid: (advantage(mid), mid))
    chosen_id = ranked[(len(ranked) - 1) // 2]
    advantages = [advantage(mid) for mid in ranked]
    spec = next(m for m in world.mandates if m.mandate_id == chosen_id)

    payload = {
        "seed": SEED,
        "n_customers": n_customers,
        "selection": {
            "criteria": SELECTION_CRITERIA,
            "n_candidates": len(candidates),
            "n_mandates": n_customers,
            "net_ltv_advantage_inr": {
                "chosen": advantage(chosen_id),
                "p25": _quantile(advantages, 0.25),
                "median": _quantile(advantages, 0.5),
                "p75": _quantile(advantages, 0.75),
            },
        },
        "mandate": {
            "mandate_id": spec.mandate_id,
            "bank_id": spec.customer.bank_id,
            "method": "upi_autopay",
            "merchant_category": spec.merchant_category,
            "amount": spec.amount,
            "cycle_day": spec.cycle_day,
        },
        "lanes": {
            Arm.AGGRESSIVE_8X.value: _lane(aggressive[chosen_id]),
            Arm.DOBARA.value: _lane(dobara[chosen_id]),
        },
        "provenance": stamp(),
    }

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(payload, indent=2))
    print(
        f"wrote {OUT_PATH} ({OUT_PATH.stat().st_size / 1024:.1f} KB) -- "
        f"mandate {chosen_id} of {len(candidates)} candidates"
    )


if __name__ == "__main__":
    main()
