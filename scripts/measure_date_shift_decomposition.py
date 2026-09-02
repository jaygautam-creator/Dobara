"""Persists the date-shift decomposition measured ad hoc during this session's
diagnosis (docs/DECISIONS.md [2026-09-02] "Diagnosing the reversal") and reported only
in prose in README.md / docs/DECISIONS.md -- never written to a committed artifact,
the same gap `scripts/measure_production_tie_rate.py` closed for the tie-rate figure.

For every decision in the held-out world (`api/demo.py`'s DEMO_SEED/DEMO_N_CUSTOMERS)
where the argmax's legal-candidate set has 2+ alternatives, scores it under BOTH the
isotonic and Platt production calibrators and classifies the change:
- "action_type_changed": the chosen action's TYPE differs (e.g. Stop vs ScheduleDebit).
- "date_changed": both chose a ScheduleDebit, but a different day `t`.
- "unchanged": identical choice.

For every "date_changed" decision, records the signed day delta (Platt's date minus
isotonic's date) so the direction and magnitude are measured, not asserted.

Read-only, no retraining. Writes `artifacts/date_shift_decomposition.json`.
"""

from __future__ import annotations

import dataclasses
import json

import joblib

from agent.actions import OfferDateChange, ScheduleDebit
from agent.audit import AuditRecord, AuditTrail
from agent.compliance import is_hard_compliant
from agent.decide import _generate_candidates, _score_all
from agent.models import ModelBundle, load_model_bundle
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
PLATT_MODEL_VERSION = "46abfd4c9c02"
DEMO_SEED = 9001
DEMO_N_CUSTOMERS = 150
OUT_PATH = "artifacts/date_shift_decomposition.json"


def _action_type(action: object) -> str:
    return type(action).__name__


def main() -> None:
    params = load_params()
    policy = load_policy()

    bundle_platt = load_model_bundle(DB_PATH, ARTIFACTS_DIR)
    if bundle_platt.recovery.model_version != PLATT_MODEL_VERSION:
        raise SystemExit(
            f"installed recovery model_version is "
            f"{bundle_platt.recovery.model_version!r}, not the expected Platt version "
            f"{PLATT_MODEL_VERSION!r} -- this script is only reproducible on "
            "experiment/platt-calibrator (see module docstring)."
        )
    isotonic_calibrator = joblib.load(
        f"{ARTIFACTS_DIR}/models/recovery_lgbm_calibrator_{ISOTONIC_MODEL_VERSION}.joblib"
    )
    bundle_isotonic: ModelBundle = dataclasses.replace(
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
    records: list[AuditRecord] = list(trail.records())

    n_checked = 0
    n_action_type_changed = 0
    n_date_changed = 0
    n_unchanged = 0
    day_deltas: list[float] = []

    for r in records:
        ctx = r.ctx
        candidates = _generate_candidates(ctx, policy)
        legal = [a for a in candidates if is_hard_compliant(a, ctx, policy)]
        if len(legal) < 2:
            continue
        n_checked += 1

        scores_iso = _score_all(legal, ctx, bundle_isotonic)
        scores_platt = _score_all(legal, ctx, bundle_platt)
        nets_iso = [round(s.expected_net, 6) for s in scores_iso]
        nets_platt = [round(s.expected_net, 6) for s in scores_platt]
        chosen_iso = legal[nets_iso.index(max(nets_iso))]
        chosen_platt = legal[nets_platt.index(max(nets_platt))]

        if _action_type(chosen_iso) != _action_type(chosen_platt):
            n_action_type_changed += 1
            continue
        if isinstance(chosen_iso, ScheduleDebit) and isinstance(chosen_platt, ScheduleDebit):
            if chosen_iso.t == chosen_platt.t:
                n_unchanged += 1
            else:
                n_date_changed += 1
                day_deltas.append((chosen_platt.t - chosen_iso.t).total_seconds() / 86400.0)
        elif isinstance(chosen_iso, OfferDateChange) and isinstance(chosen_platt, OfferDateChange):
            n_unchanged += 1
        else:
            n_unchanged += 1

    n_later = sum(1 for d in day_deltas if d > 0)
    n_earlier = sum(1 for d in day_deltas if d < 0)
    sorted_deltas = sorted(day_deltas)
    median_delta = (
        sorted_deltas[len(sorted_deltas) // 2]
        if len(sorted_deltas) % 2
        else (sorted_deltas[len(sorted_deltas) // 2 - 1] + sorted_deltas[len(sorted_deltas) // 2])
        / 2
        if sorted_deltas
        else float("nan")
    )
    mean_delta = sum(day_deltas) / len(day_deltas) if day_deltas else float("nan")
    pct_later = n_later / len(day_deltas) if day_deltas else float("nan")
    date_changed_pct = n_date_changed / n_checked if n_checked else float("nan")
    action_type_changed_pct = n_action_type_changed / n_checked if n_checked else float("nan")

    day_delta_stats: dict[str, object] = {
        "n": len(day_deltas),
        "n_later": n_later,
        "n_earlier": n_earlier,
        "pct_later": pct_later,
        "median_days": median_delta,
        "mean_days": mean_delta,
        "min_days": min(day_deltas) if day_deltas else float("nan"),
        "max_days": max(day_deltas) if day_deltas else float("nan"),
    }

    report: dict[str, object] = {
        "note": (
            "Decomposes isotonic->Platt argmax changes on the held-out world "
            f"(seed={DEMO_SEED}, n={DEMO_N_CUSTOMERS}) into action-type changes vs. "
            "date-only changes among ScheduleDebit-to-ScheduleDebit decisions, and "
            "measures the signed day delta (platt_date - isotonic_date) for the latter."
        ),
        "seed": DEMO_SEED,
        "n_mandates": DEMO_N_CUSTOMERS,
        "isotonic_model_version": ISOTONIC_MODEL_VERSION,
        "platt_model_version": PLATT_MODEL_VERSION,
        "n_decisions_with_alternatives": n_checked,
        "n_action_type_changed": n_action_type_changed,
        "n_date_changed": n_date_changed,
        "n_unchanged": n_unchanged,
        "date_changed_pct_of_total": date_changed_pct,
        "action_type_changed_pct_of_total": action_type_changed_pct,
        "day_delta_stats": day_delta_stats,
    }
    report["provenance"] = stamp()
    report["content_hash"] = content_hash({k: v for k, v in report.items() if k != "provenance"})

    with open(OUT_PATH, "w") as f:
        json.dump(report, f, indent=2)
    print(f"wrote {OUT_PATH}")
    print(f"n_checked={n_checked}")
    print(f"action_type_changed={n_action_type_changed} ({action_type_changed_pct:.1%})")
    print(f"date_changed={n_date_changed} ({date_changed_pct:.1%})")
    print(
        f"of date changes: {n_later}/{len(day_deltas)} later ({pct_later:.1%}), "
        f"median {median_delta:.1f} days, mean {mean_delta:.2f} days"
    )


if __name__ == "__main__":
    main()
