"""CLI entrypoint: `python -m sim.run [--seed N] [--seeds N] [--cycles N] [--mandates N]`.

Runs the simulator and prints a validation summary against the published benchmarks in
docs/04-DATA-MODEL.md (failure rate, recovery rate, revocation ratio) so a drifted
calibration is visible immediately rather than discovered downstream in `make eval`.
"""

from __future__ import annotations

import argparse

from sim.engine import default_db_path, run_simulation
from sim.params import load_params

# Benchmark ranges from docs/04-DATA-MODEL.md calibration anchors table. Wide on purpose —
# this is a sanity check, not a strict statistical test (that lives in Phase 2's validation
# suite once splits + the full 30-seed run exist).
BENCHMARKS = {
    "failure_rate": (0.04, 0.22),  # 4-6% B2B / 6-10% B2C dunning benchmarks; AutoPay skews
    # higher because these are bank-initiated recurring debits, not customer-initiated.
    # Upper bound widened past the raw dunning-benchmark ceiling because AutoPay executions
    # are not directly comparable to customer-initiated dunning (docs/04-DATA-MODEL.md).
    "recovery_rate": (0.15, 0.75),  # avg 30-45%, top quartile 55-70%, wide band for one seed
    "monthly_revocation_ratio": (0.01, 0.15),  # sanity band, not a tight NPCI match at this scale
}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--seeds", type=int, default=1, help="if >1, runs seed 0..seeds-1")
    parser.add_argument("--cycles", type=int, default=None)
    parser.add_argument("--mandates", "--customers", dest="customers", type=int, default=None)
    parser.add_argument("--merchants", type=int, default=None)
    parser.add_argument("--out", type=str, default=None)
    args = parser.parse_args()

    params = load_params()
    seeds = [args.seed] if args.seed is not None else list(range(args.seeds))

    for seed in seeds:
        db_path = args.out or default_db_path(seed)
        summary = run_simulation(
            params,
            seed=seed,
            db_path=db_path,
            n_customers=args.customers,
            n_cycles=args.cycles,
            n_merchants=args.merchants,
        )
        print(f"--- seed={seed} -> {db_path} ---")
        print(summary)
        print(f"failure_rate={summary.failure_rate:.3f}")
        print(f"recovery_rate={summary.recovery_rate:.3f}")
        print(f"monthly_revocation_ratio={summary.monthly_revocation_ratio:.3f}")

        for metric, (lo, hi) in BENCHMARKS.items():
            value = getattr(summary, metric)
            flag = "OK" if lo <= value <= hi else "OUT OF RANGE"
            print(f"  benchmark check [{metric}]: {value:.3f} in [{lo}, {hi}] -> {flag}")


if __name__ == "__main__":
    main()
