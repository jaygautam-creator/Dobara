"""Measures the argmax tie rate under the PRODUCTION `PlattCalibrator`
(`models/recovery.py`'s `lgbm_calibrator` as actually persisted and loaded by
`agent/models.py::load_model_bundle` -- fit on the FULL validate split, not the
half-split fit `scripts/calibrator_bakeoff.py`/`scripts/held_out_calibrator_verification.py`
use for a fair Brier comparison against candidate calibrators under evaluation).

This number (77.2% isotonic -> ~18% Platt, production) was measured ad hoc during this
session's diagnosis and reported in prose in `docs/DECISIONS.md` [2026-09-02] and the
README's calibrator-experiment section, but never written to a committed artifact --
a gap inconsistent with this repo's own "every number needs a stated source" rule.
This script closes it: read-only, no retraining (loads both persisted model versions'
joblib artifacts as-is), writes `artifacts/production_tie_rate.json`.
"""

from __future__ import annotations

import dataclasses
import json

import joblib

from agent.audit import AuditTrail
from agent.compliance import is_hard_compliant
from agent.decide import _generate_candidates, _score_all
from agent.models import load_model_bundle
from agent.policy import load_policy
from eval.arms import Arm
from eval.provenance import content_hash, stamp
from eval.runner import run_arm
from eval.world import build_world
from models.ltv import build_life_table
from sim.params import load_params

DB_PATH = "data/dobara.sqlite3"
ARTIFACTS_DIR = "artifacts"
ISOTONIC_MODEL_VERSION = "e5eaa66718f2"
DEMO_SEED = 9001
DEMO_N_CUSTOMERS = 150
OUT_PATH = "artifacts/production_tie_rate.json"


def _tie_rate(records: list, policy: object, bundle: object) -> dict[str, object]:
    n_with_alt = 0
    n_tied = 0
    for r in records:
        ctx = r.ctx
        candidates = _generate_candidates(ctx, policy)
        legal = [a for a in candidates if is_hard_compliant(a, ctx, policy)]
        if len(legal) < 2:
            continue
        scores = _score_all(legal, ctx, bundle)
        nets = [round(s.expected_net, 6) for s in scores]
        best = max(nets)
        n_with_alt += 1
        if nets.count(best) > 1:
            n_tied += 1
    rate = n_tied / n_with_alt if n_with_alt else float("nan")
    return {
        "n_decisions_with_alternatives": n_with_alt,
        "n_tied_at_argmax": n_tied,
        "tie_rate": rate,
    }


def main() -> None:
    params = load_params()
    policy = load_policy()

    # The Platt-calibrated production bundle -- this branch's checked-in artifacts.
    bundle_platt = load_model_bundle(DB_PATH, ARTIFACTS_DIR)

    # The isotonic-calibrated production bundle -- the model version this experiment
    # branch superseded, its own joblib artifacts still present on disk here.
    isotonic_calibrator = joblib.load(
        f"{ARTIFACTS_DIR}/models/recovery_lgbm_calibrator_{ISOTONIC_MODEL_VERSION}.joblib"
    )
    bundle_isotonic = dataclasses.replace(
        bundle_platt,
        recovery=dataclasses.replace(bundle_platt.recovery, lgbm_calibrator=isotonic_calibrator),
    )

    life_table = build_life_table(DB_PATH, int(params.get("ltv.horizon_cycles")))
    world = build_world(params, seed=DEMO_SEED, n_customers=DEMO_N_CUSTOMERS)
    trail = AuditTrail()
    run_arm(
        world,
        Arm.DOBARA,
        params,
        life_table,
        policy=policy,
        model_bundle=bundle_platt,
        holdout_fraction=0.0,
        audit_trail=trail,
    )
    records = list(trail.records())
    attempt1_records = [r for r in records if r.ctx.attempt_index == 1]

    report: dict[str, object] = {
        "note": (
            "Argmax tie rate under each PRODUCTION calibrator (full-validate-split fit, "
            "as actually persisted/loaded by agent/models.py -- not the half-split "
            "fit scripts/calibrator_bakeoff.py uses for a fair Brier comparison), "
            "measured on the held-out world api/demo.py uses (DEMO_SEED=9001, "
            f"n={DEMO_N_CUSTOMERS})."
        ),
        "seed": DEMO_SEED,
        "n_mandates": DEMO_N_CUSTOMERS,
        "isotonic_model_version": ISOTONIC_MODEL_VERSION,
        "platt_model_version": bundle_platt.recovery.model_version,
        "slices": {
            "all_decisions_with_alternatives": {
                "isotonic": _tie_rate(records, policy, bundle_isotonic),
                "platt": _tie_rate(records, policy, bundle_platt),
            },
            "attempt_index_1_only": {
                "isotonic": _tie_rate(attempt1_records, policy, bundle_isotonic),
                "platt": _tie_rate(attempt1_records, policy, bundle_platt),
            },
        },
    }
    report["provenance"] = stamp()
    report["content_hash"] = content_hash({k: v for k, v in report.items() if k != "provenance"})

    with open(OUT_PATH, "w") as f:
        json.dump(report, f, indent=2)
    print(f"wrote {OUT_PATH}")
    for slice_name, slice_data in report["slices"].items():
        iso = slice_data["isotonic"]["tie_rate"]
        platt = slice_data["platt"]["tie_rate"]
        print(f"{slice_name}: isotonic {iso:.1%} -> platt {platt:.1%}")


if __name__ == "__main__":
    main()
