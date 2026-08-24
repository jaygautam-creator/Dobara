"""CLI entrypoint: `python -m sim.run [--seed N] [--seeds N] [--cycles N] [--mandates N]`.

Runs the simulator and prints a validation summary against the published benchmarks in
docs/04-DATA-MODEL.md (failure rate, recovery rate, revocation ratio) so a drifted
calibration is visible immediately rather than discovered downstream in `make eval`.
"""

from __future__ import annotations

import argparse

from sim.engine import default_db_path, run_simulation
from sim.params import load_params

# The canonical single-run artifact `make train`/`make eval` read by convention when no
# explicit --seed sweep or --out is requested. Multi-seed sweeps (--seeds N>1) keep the
# per-seed suffixed naming from sim.engine.default_db_path.
CANONICAL_DB_PATH = "data/dobara.sqlite3"

# Benchmark ranges from docs/04-DATA-MODEL.md calibration anchors table. These are
# per-seed sanity bands for human eyeballing during `make sim` — they print but never
# fail the run. The real gate is tests/test_calibration.py, which asserts the MEAN across
# 5 seeds against these same bands and fails CI on a calibration regression.
BENCHMARKS = {
    "failure_rate": (0.04, 0.22),  # 4-6% B2B / 6-10% B2C dunning benchmarks; AutoPay skews
    # higher because these are bank-initiated recurring debits, not customer-initiated.
    # Upper bound widened past the raw dunning-benchmark ceiling because AutoPay executions
    # are not directly comparable to customer-initiated dunning (docs/04-DATA-MODEL.md).
    "recovery_rate": (0.28, 0.48),  # published avg 30-45%, top quartile 55-70%; tightened
    # 2026-08-25 from an original (0.15, 0.75) band once the revocation recalibration
    # (below) pulled the simulated mean to ~41%, comfortably inside the avg band with
    # headroom for per-seed variance. See docs/DECISIONS.md.
    "monthly_revocation_ratio": (0.01, 0.30),  # loose sanity band on revocations/mandate
    # over the full 8-cycle run; not a direct NPCI comparison (that unit is per-month).
    "revocation_per_execution_ratio": (0.015, 0.04),  # the harder benchmark: revocations /
    # mandate executions ≈ 20M/month ÷ 808M/month ≈ 2.5% (both pinned in
    # docs/04-DATA-MODEL.md). A target ratio with caveats, not a precision constant — see
    # the note in sim/params.yaml's revocation block.
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
    single_default_run = args.seed is None and args.seeds == 1
    if single_default_run:
        seeds = [params.get("rng.seed_default")]
    elif args.seed is not None:
        seeds = [args.seed]
    else:
        seeds = list(range(args.seeds))

    for seed in seeds:
        if args.out:
            db_path = args.out
        elif single_default_run:
            db_path = CANONICAL_DB_PATH
        else:
            db_path = default_db_path(seed)
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
