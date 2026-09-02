"""Measures the argmax tie rate under the PRODUCTION `PlattCalibrator`
(`models/recovery.py`'s `lgbm_calibrator` as actually persisted and loaded by
`agent/models.py::load_model_bundle` -- fit on the FULL validate split, not the
half-split fit `scripts/calibrator_bakeoff.py`/`scripts/held_out_calibrator_verification.py`
use for a fair Brier comparison against candidate calibrators under evaluation).

This number (75.7% isotonic -> 17.9% Platt, production, all-decisions slice) was
measured ad hoc during this session's diagnosis and reported in prose in
`docs/DECISIONS.md` [2026-09-02] and the README's calibrator-experiment section, but
never written to a committed artifact -- a gap inconsistent with this repo's own
"every number needs a stated source" rule. This script closes it: read-only, no
retraining (loads both persisted model versions' joblib artifacts as-is), writes
`artifacts/production_tie_rate.json`.

**Cross-branch note, cherry-picked onto `main` 2026-09-02 (docs/DECISIONS.md
[2026-09-02] "Third number collision"): this script cannot be re-run to completion on
a clean `main` checkout alone.** `main`'s `models/recovery.py` does not define
`PlattCalibrator` (isotonic ships; the calibrator-experiment branch's class was never
merged) and `main`'s `artifacts/models/` does not carry the Platt joblib files
(`recovery_lgbm_calibrator_46abfd4c9c02.joblib` and friends) -- both live only on
`experiment/platt-calibrator`, where this script was originally run and where it
remains fully reproducible (`git checkout experiment/platt-calibrator`). The committed
`artifacts/production_tie_rate.json` on `main` is the pinned, authoritative record of
that branch's measurement, carrying its own `provenance.git_commit`; it is not
re-derivable from `main`'s own state, by design -- the experiment it measures was
deliberately not shipped to `main`. Reading the committed JSON (no script execution
required) is the correct way to verify a figure cited from it on `main`.
"""

from __future__ import annotations

import dataclasses
import json

import joblib

from agent.audit import AuditRecord, AuditTrail
from agent.compliance import is_hard_compliant
from agent.decide import _generate_candidates, _score_all
from agent.models import ModelBundle, load_model_bundle
from agent.policy import PolicyConfig, load_policy
from eval.arms import Arm
from eval.provenance import content_hash, stamp
from eval.runner import run_arm
from eval.world import build_world
from models.ltv import build_life_table
from sim.params import load_params

DB_PATH = "data/dobara.sqlite3"
ARTIFACTS_DIR = "artifacts"
ISOTONIC_MODEL_VERSION = "e5eaa66718f2"
PLATT_MODEL_VERSION = "46abfd4c9c02"
DEMO_SEED = 9001
DEMO_N_CUSTOMERS = 150
OUT_PATH = "artifacts/production_tie_rate.json"


def _tie_rate(
    records: list[AuditRecord], policy: PolicyConfig, bundle: ModelBundle
) -> dict[str, object]:
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
    # Fail loudly, not silently: on a checkout where the installed recovery model
    # isn't actually the Platt version (e.g. `main`, which ships isotonic --
    # confirmed the hard way: `load_model_bundle` here would otherwise silently
    # return the isotonic bundle under the "bundle_platt" name, and this script would
    # go on to compare isotonic against itself and write a wrong, misleading
    # artifact with no error at all), stop here instead of producing bad output.
    if bundle_platt.recovery.model_version != PLATT_MODEL_VERSION:
        raise SystemExit(
            f"installed recovery model_version is {bundle_platt.recovery.model_version!r}, "
            f"not the expected Platt version {PLATT_MODEL_VERSION!r} -- this script is only "
            "reproducible on experiment/platt-calibrator (see module docstring); the "
            "committed artifacts/production_tie_rate.json is the authoritative record on "
            "other branches, not something to regenerate here."
        )

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

    slices: dict[str, dict[str, dict[str, object]]] = {
        "all_decisions_with_alternatives": {
            "isotonic": _tie_rate(records, policy, bundle_isotonic),
            "platt": _tie_rate(records, policy, bundle_platt),
        },
        "attempt_index_1_only": {
            "isotonic": _tie_rate(attempt1_records, policy, bundle_isotonic),
            "platt": _tie_rate(attempt1_records, policy, bundle_platt),
        },
    }
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
        "slices": slices,
    }
    report["provenance"] = stamp()
    report["content_hash"] = content_hash({k: v for k, v in report.items() if k != "provenance"})

    with open(OUT_PATH, "w") as f:
        json.dump(report, f, indent=2)
    print(f"wrote {OUT_PATH}")
    for slice_name, slice_data in slices.items():
        iso = slice_data["isotonic"]["tie_rate"]
        platt = slice_data["platt"]["tie_rate"]
        assert isinstance(iso, float) and isinstance(platt, float)
        print(f"{slice_name}: isotonic {iso:.1%} -> platt {platt:.1%}")


if __name__ == "__main__":
    main()
