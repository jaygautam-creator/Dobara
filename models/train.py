"""CLI entrypoint: `python -m models.train [--db PATH] [--out DIR]`.

Runs, against an existing simulated database (from `make sim`): bank health, the recovery
model, the revocation hazard model, and builds the LTV life table. Model versions and
headline numbers print to stdout; full reports land in `--out` as JSON.
"""

from __future__ import annotations

import argparse
import json

from models.bank_health import compute_bank_health_snapshots
from models.hazard import train_hazard_model
from models.ltv import build_life_table
from models.recovery import train_recovery_model
from sim.params import load_params


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=str, default="data/dobara.sqlite3")
    parser.add_argument("--out", type=str, default="artifacts")
    args = parser.parse_args()

    n_snapshots = compute_bank_health_snapshots(args.db)
    print(f"bank_health: {n_snapshots} snapshots written")

    print("\n=== Model 1: Recovery ===")
    recovery_report = train_recovery_model(args.db, out_dir=args.out)
    print(f"model_version={recovery_report['model_version']}")
    print(
        f"  train={recovery_report['n_train']} validate={recovery_report['n_validate']} "
        f"test={recovery_report['n_test']} cold_start={recovery_report['n_cold_start']}"
    )
    print(f"  beats_baseline={recovery_report['beats_baseline']}")
    for model_key in ("lightgbm", "logistic_baseline"):
        b = recovery_report[model_key]["calibrated"]["brier_score"]
        auc = recovery_report[model_key]["calibrated"]["roc_auc"]
        print(
            f"  {model_key}: brier={b['point']:.4f} [{b['ci_lo']:.4f}, {b['ci_hi']:.4f}] "
            f"auc={auc['point']:.4f} [{auc['ci_lo']:.4f}, {auc['ci_hi']:.4f}]"
        )
    regime = recovery_report["slices"]["by_regime_shift_bank"].get("True")
    if regime and "brier_score" in regime:
        print(
            f"  regime_shift_bank slice: brier={regime['brier_score']['point']:.4f} "
            f"(n={regime['n']}) — reported separately, not folded into the headline"
        )
    print(f"full report: {args.out}/recovery_model_report.json")

    print("\n=== Model 2: Revocation hazard ===")
    hazard_report = train_hazard_model(args.db, out_dir=args.out)
    print(f"model_version={hazard_report['model_version']}")
    print(
        f"  train={hazard_report['n_train']} validate={hazard_report['n_validate']} "
        f"test={hazard_report['n_test']} cold_start={hazard_report['n_cold_start']}"
    )
    b = hazard_report["calibrated"]["brier_score"]
    auc = hazard_report["calibrated"]["roc_auc"]
    print(f"  brier={b['point']:.4f} [{b['ci_lo']:.4f}, {b['ci_hi']:.4f}] auc={auc['point']:.4f}")
    headline = hazard_report["headline_marginal_hazard"]["mean_hazard_by_failure_count"]
    print("  headline: mean hazard by failure-notification count this cycle:")
    for k in sorted(headline, key=int):
        h = headline[k]["mean_hazard"]
        n = headline[k]["n"]
        print(f"    {k} prior failures: hazard={h:.4f} (n={n})")
    print(f"full report: {args.out}/hazard_model_report.json")

    print("\n=== LTV life table ===")
    params = load_params()
    table = build_life_table(args.db, horizon_cycles=params.get("ltv.horizon_cycles"))
    categories = sorted({cat for cat, _ in table.survival})
    print(f"categories: {categories}")
    life_table_json = {
        "horizon_cycles": table.horizon_cycles,
        "margin_factor_assumption": params.get("ltv.margin_factor"),
        "survival": {f"{cat}|{age}": s for (cat, age), s in table.survival.items()},
    }
    with open(f"{args.out}/ltv_life_table.json", "w") as f:
        json.dump(life_table_json, f, indent=2)
    print(f"life table: {args.out}/ltv_life_table.json")


if __name__ == "__main__":
    main()
