"""Phase 4 batch evaluation harness entrypoint — `make eval` runs `python -m eval.run`.
Per docs/07-EVAL-SPEC.md: runs all 5 arms (`eval/arms.py::Arm`) over 30 identically-seeded
held-out populations (`eval/world.py::build_world`, seeds distinct from the seed=42
population `sim.run` used to generate Phase 1/2's training data), writes
`artifacts/results.parquet` (one row per seed x arm x mandate — the full row-level record,
so any slice can be recomputed later without rerunning the harness) and
`artifacts/summary.json` (the aggregated, CI-bearing numbers the README/UI are meant to
quote verbatim, never hand-typed, per the spec's reproducibility section).

**Headline comparison is `dobara` vs `razorpay_default`, never `aggressive_8x`** — the
latter is the arm that demonstrates the retry-hazard mechanism (up to 8 retries = 8
mandatory notifications = compounding revocation hazard), not the credible claim; if it
collapses on net LTV relative to `razorpay_default`, `summary.json` records that as a
one-line mechanical fact, not a "win" against a strawman.

**Metric aggregation, stated explicitly (declared choices, not the only defensible
ones):** each of the nine `docs/07-EVAL-SPEC.md` metrics is computed **per seed** (a
single total/mean/rate over that seed's ~5000-mandate population for a given arm), then
bootstrap-percentile-CI'd across the 30 per-seed values (`eval/metrics.py::bootstrap_mean_ci`,
reusing `models/metrics.py`'s `RNG_SEED`/`N_BOOTSTRAP`) — this is exactly the shape
docs/07-EVAL-SPEC.md's example line asks for ("₹4.2L recovered [95% CI ...], n=30
seeds"). **`recovery_rate_of_failed_cycles`** is the spec's own metric-table definition
("Recovery rate % | Of failed cycles") — `n_cycles_with_failure_then_recovery /
n_cycles_with_failure`, tracked per-cycle in `eval/runner.py::MandateResult` and
`_end_of_cycle`, matching `sim.engine.SimSummary.recovery_rate` exactly (the same metric
Phase 1's calibration gate asserts in `(0.28, 0.48)`) — this is the metric any README text
must quote as "recovery rate." A separate `mandate_ever_recovered_rate` (a mandate-*
lifetime* proxy: of mandates needing more than one attempt across their whole run, the
fraction that ever succeeded) is reported alongside for continuity but must never be
called "recovery rate" — the two have different denominators and are not comparable
numbers. (Before 2026-08-25 this harness only computed the lifetime proxy under the name
`recovery_rate`, which is why an early run showed 0.97-1.00 against a >1.0-incompatible
Phase 1 benchmark of 0.28-0.48 — see docs/DECISIONS.md.) Paired `dobara - razorpay_default`
comparisons use the same-seed per-seed net-LTV totals (`docs/07-EVAL-SPEC.md`: "Paired
comparisons between arms use the same seeds"), bootstrapped over the 30 paired
differences, not two independent CIs compared informally.

**Robustness slices** (per bank incl. the regime-shift bank, per method, per attempt
index, cold-start, outage windows) are computed on the full pooled 30-seed x mandate
row-level data for `dobara` and `razorpay_default`, reported as simple recovery-rate /
mean-net-LTV comparisons per slice — not independently seed-bootstrapped per slice, for
tractability within this session's time budget; this is stated explicitly in
`summary.json` rather than presented with a CI it doesn't have.

**The permanent holdout arm** (`config/policy.yaml`'s `holdout_fraction`, wired in
`eval/runner.py::_run_dobara_arm`) is reported as its own slice within the `dobara` arm's
rows (`routed_to_holdout` column) — recovery lift is the served (non-holdout) population
against this same-seed, same-population holdout control, never folded into `dobara`'s
own aggregate.
"""

from __future__ import annotations

import json
import math
import time
from pathlib import Path
from typing import Any

import pandas as pd
from joblib import Parallel, delayed

from agent.models import ModelBundle, load_model_bundle
from agent.policy import PolicyConfig, load_policy
from eval.arms import Arm
from eval.metrics import bootstrap_mean_ci
from eval.runner import MandateResult, run_arm
from eval.world import build_world
from models.ltv import LifeTable, build_life_table
from sim.params import Params, load_params

TRAIN_DB_PATH = "data/dobara.sqlite3"
ARTIFACTS_DIR = Path("artifacts")
N_SEEDS = 30
# Distinct from the seed=42 population `sim.run` used for Phase 1/2 training data, and
# from the smaller ad-hoc seeds used during Phase 4 development (1, 9001) — a genuinely
# held-out block, per docs/04-DATA-MODEL.md "held-out batch".
SEEDS = list(range(101, 101 + N_SEEDS))


def _result_row(seed: int, arm: str, r: MandateResult) -> dict[str, Any]:
    return {
        "seed": seed,
        "arm": arm,
        "mandate_id": r.mandate_id,
        "bank_id": r.bank_id,
        "method": r.method,
        "merchant_category": r.merchant_category,
        "is_cold_start": r.is_cold_start,
        "regime_shift_bank": r.regime_shift_bank,
        "amount": r.amount,
        "n_attempts": r.n_attempts,
        "n_successes": r.n_successes,
        "n_notifications": r.n_notifications,
        "n_hard_declines": r.n_hard_declines,
        "n_human_escalations": r.n_human_escalations,
        "n_abstentions": r.n_abstentions,
        "gross_recovered_inr": r.gross_recovered_inr,
        "notification_cost_inr": r.notification_cost_inr,
        "revoked": r.revoked,
        "revoked_at_cycle": r.revoked_at_cycle,
        "ltv_lost_inr": r.ltv_lost_inr,
        "attempts_in_outage_window": r.attempts_in_outage_window,
        "routed_to_holdout": r.routed_to_holdout,
        "net_ltv_inr": r.net_ltv_inr,
        "first_success_attempt_index": (
            r.success_attempt_indices[0] if r.success_attempt_indices else None
        ),
        "n_cycles_with_failure": r.n_cycles_with_failure,
        "n_cycles_with_failure_then_recovery": r.n_cycles_with_failure_then_recovery,
        "attempts_in_failed_cycles": r.attempts_in_failed_cycles,
    }


def _run_one_seed(
    seed: int,
    n_customers: int,
    n_merchants: int,
    params: Params,
    policy: PolicyConfig,
    model_bundle: ModelBundle,
    life_table: LifeTable,
    holdout_fraction: float,
) -> list[dict[str, Any]]:
    world = build_world(params, seed=seed, n_customers=n_customers, n_merchants=n_merchants)
    rows: list[dict[str, Any]] = []
    for arm in Arm:
        kwargs: dict[str, Any] = {}
        if arm is Arm.DOBARA:
            kwargs = {
                "policy": policy,
                "model_bundle": model_bundle,
                "holdout_fraction": holdout_fraction,
            }
        results = run_arm(world, arm, params, life_table, **kwargs)
        rows.extend(_result_row(seed, arm.value, r) for r in results)
    return rows


def _per_seed_totals(df: pd.DataFrame, arm: str) -> pd.DataFrame:
    a = df[df["arm"] == arm]

    def _recovery_rate_of_failed_cycles(g: pd.DataFrame) -> float:
        """The docs/07-EVAL-SPEC.md metric-table definition ("Recovery rate % | Of failed
        cycles"), matching `sim.engine.SimSummary.recovery_rate` exactly
        (n_cycles_with_failure_then_recovery / n_cycles_with_failure) -- this is what
        Phase 1's calibration gate (`tests/test_calibration.py`, band (0.28, 0.48))
        asserts on the training population, and what any README text must quote. NOT the
        same denominator as `mandate_ever_recovered_rate` below -- see docs/DECISIONS.md
        [2026-08-25] "recovery-rate metric: two definitions, now distinct".
        """
        denom = g["n_cycles_with_failure"].sum()
        if denom == 0:
            return float("nan")
        return float(g["n_cycles_with_failure_then_recovery"].sum()) / float(denom)

    def _mandate_ever_recovered_rate(g: pd.DataFrame) -> float:
        """The pre-2026-08-25 proxy metric, kept under an unambiguous name for
        continuity/comparison only -- of mandates that needed more than one attempt
        across their whole simulated lifetime (not one cycle), the fraction that ever
        succeeded at all. This is NOT the spec's "of failed cycles" metric and must never
        be reported as `recovery_rate` or quoted in a README."""
        denom = (g["n_attempts"] > 1).sum()
        if denom == 0:
            return float("nan")
        return float(((g["n_attempts"] > 1) & (g["n_successes"] > 0)).sum()) / float(denom)

    def _attempts_mean_in_failed_cycles(g: pd.DataFrame) -> float:
        """Mean attempts actually used in cycles whose first attempt failed -- the metric
        that reflects a cadence's retry ceiling, unlike the lifetime `attempts_mean`
        below (diluted by the ~90% of cycles that never fail at all, and by
        revocation-driven early truncation of a mandate's remaining cycles). See
        docs/DECISIONS.md [2026-08-25] "aggressive_8x investigation"."""
        denom = g["n_cycles_with_failure"].sum()
        if denom == 0:
            return float("nan")
        return float(g["attempts_in_failed_cycles"].sum()) / float(denom)

    per_seed = a.groupby("seed").apply(
        lambda g: pd.Series(
            {
                "gross_recovered_inr": g["gross_recovered_inr"].sum(),
                "recovery_rate_of_failed_cycles": _recovery_rate_of_failed_cycles(g),
                "mandate_ever_recovered_rate": _mandate_ever_recovered_rate(g),
                "attempts_mean": g["n_attempts"].mean(),
                "attempts_mean_in_failed_cycles": _attempts_mean_in_failed_cycles(g),
                "notifications_total": g["n_notifications"].sum(),
                "revocations_total": g["revoked"].sum(),
                "net_ltv_total": g["net_ltv_inr"].sum(),
                "human_escalations_total": g["n_human_escalations"].sum(),
                "abstentions_total": g["n_abstentions"].sum(),
            }
        ),
        include_groups=False,
    )
    per_seed["recovered_per_notification"] = (
        per_seed["gross_recovered_inr"] / per_seed["notifications_total"]
    )
    return per_seed


def _json_safe(obj: Any) -> Any:
    """Recursively replaces `float("nan")` with `None` (JSON `null`) before
    serialization. `bootstrap_mean_ci`/several rate calculations below use `nan` as the
    internal "genuinely undefined" sentinel (e.g. `do_nothing`'s
    `recovery_rate_of_failed_cycles`, undefined because it makes zero attempts, not
    zero) -- that's a fine internal convention, but `json.dumps` has no native NaN and
    Python's default `allow_nan=True` writes a bare `NaN` token that is not valid JSON
    and every strict parser (including a browser's own `JSON.parse`) rejects. Fixed at
    the producer, not at each consumer: `artifacts/summary.json` is a public evidence
    artifact served verbatim by `/evidence/summary`, so it must be valid JSON on its own,
    not merely readable by Python's own permissive `json.load`. `main()` calls this once
    on the whole `summary` dict, then serializes with `allow_nan=False` as a backstop --
    any NaN this function's recursion doesn't reach fails loudly instead of silently
    reproducing this bug.
    """
    if isinstance(obj, float) and math.isnan(obj):
        return None
    if isinstance(obj, dict):
        return {k: _json_safe(v) for k, v in obj.items()}
    if isinstance(obj, list | tuple):
        return [_json_safe(v) for v in obj]
    return obj


def _metric_block(per_seed: pd.DataFrame) -> dict[str, Any]:
    block = {}
    for col in per_seed.columns:
        vals = per_seed[col].dropna().to_numpy()
        point, lo, hi = bootstrap_mean_ci(vals)
        block[col] = {"point": point, "ci_lo": lo, "ci_hi": hi, "n_seeds": int(len(vals))}
    return block


def _arm_summary(df: pd.DataFrame, arm: str) -> dict[str, Any]:
    return _metric_block(_per_seed_totals(df, arm))


def _paired_diff(df: pd.DataFrame, arm_a: str, arm_b: str, metric: str) -> dict[str, Any]:
    a = _per_seed_totals(df, arm_a)[metric]
    b = _per_seed_totals(df, arm_b)[metric]
    paired = a.align(b, join="inner")
    diffs = (paired[0] - paired[1]).dropna().to_numpy()
    point, lo, hi = bootstrap_mean_ci(diffs)
    return {
        "metric": metric,
        "arm_a": arm_a,
        "arm_b": arm_b,
        "mean_diff": point,
        "ci_lo": lo,
        "ci_hi": hi,
        "significant": not (lo <= 0.0 <= hi),
        "n_paired_seeds": int(len(diffs)),
    }


def _slice_recovery_and_net_ltv(df: pd.DataFrame, arm: str, group_col: str) -> dict[str, Any]:
    """Slice-level `mandate_recovered_rate` -- of mandates in this slice, the fraction
    ever successfully collected at least once across their simulated lifetime. A
    mandate-level question ("how many mandates in this bank ever got paid"), distinct
    from the arm-level `recovery_rate_of_failed_cycles` in `_per_seed_totals` (a
    per-cycle question) -- named differently on purpose, see docs/DECISIONS.md
    [2026-08-25] "recovery-rate metric: two definitions, now distinct".
    """
    a = df[df["arm"] == arm]
    out: dict[str, Any] = {}
    for key, g in a.groupby(group_col, observed=True):
        n = len(g)
        recovered = int((g["n_successes"] > 0).sum())
        out[str(key)] = {
            "n_mandates": n,
            "mandate_recovered_rate": recovered / n if n else float("nan"),
            "mean_net_ltv_inr": float(g["net_ltv_inr"].mean()) if n else float("nan"),
            "revocations": int(g["revoked"].sum()),
        }
    return out


def _slice_attempt_index(df: pd.DataFrame, arm: str) -> dict[str, Any]:
    a = df[(df["arm"] == arm) & df["first_success_attempt_index"].notna()]
    counts = a["first_success_attempt_index"].astype(int).value_counts().sort_index()
    return {str(k): int(v) for k, v in counts.items()}


def _slice_outage(df: pd.DataFrame, arm: str) -> dict[str, Any]:
    """See `_slice_recovery_and_net_ltv`'s docstring -- `mandate_recovered_rate` here too."""
    a = df[df["arm"] == arm]
    in_outage = a[a["attempts_in_outage_window"] > 0]
    not_outage = a[a["attempts_in_outage_window"] == 0]
    return {
        "attempts_touched_an_outage_window": {
            "n_mandates": len(in_outage),
            "mandate_recovered_rate": (
                float((in_outage["n_successes"] > 0).mean()) if len(in_outage) else float("nan")
            ),
        },
        "no_outage_window": {
            "n_mandates": len(not_outage),
            "mandate_recovered_rate": (
                float((not_outage["n_successes"] > 0).mean()) if len(not_outage) else float("nan")
            ),
        },
    }


def _holdout_slice(df: pd.DataFrame) -> dict[str, Any]:
    dobara = df[df["arm"] == Arm.DOBARA.value]
    served = dobara[~dobara["routed_to_holdout"]]
    holdout = dobara[dobara["routed_to_holdout"]]
    return {
        "served_population": {
            "n_mandates": len(served),
            "mandate_recovered_rate": (
                float((served["n_successes"] > 0).mean()) if len(served) else None
            ),
            "mean_net_ltv_inr": float(served["net_ltv_inr"].mean()) if len(served) else None,
        },
        "holdout_control_population": {
            "n_mandates": len(holdout),
            "mandate_recovered_rate": (
                float((holdout["n_successes"] > 0).mean()) if len(holdout) else None
            ),
            "mean_net_ltv_inr": float(holdout["net_ltv_inr"].mean()) if len(holdout) else None,
        },
        "note": (
            "holdout_control_population is routed through razorpay_default's cadence "
            "instead of dobara's live decide(), per docs/07-EVAL-SPEC.md's permanent "
            "holdout arm -- this is the control the served population's recovery lift is "
            "measured against, and is never folded into dobara's own aggregate above."
        ),
    }


def main() -> None:
    t_start = time.time()
    params = load_params()
    policy = load_policy()
    n_customers = int(params.get("population.n_customers"))
    n_merchants = int(params.get("population.n_merchants"))
    horizon_cycles = int(params.get("ltv.horizon_cycles"))
    holdout_fraction = float(policy.get("holdout_fraction"))

    model_bundle = load_model_bundle(TRAIN_DB_PATH)
    life_table = build_life_table(TRAIN_DB_PATH, horizon_cycles)

    print(f"Running {N_SEEDS} seeds x {len(list(Arm))} arms at n_customers={n_customers}...")
    all_rows: list[list[dict[str, Any]]] = Parallel(n_jobs=-1, verbose=10)(
        delayed(_run_one_seed)(
            seed,
            n_customers,
            n_merchants,
            params,
            policy,
            model_bundle,
            life_table,
            holdout_fraction,
        )
        for seed in SEEDS
    )
    rows = [r for seed_rows in all_rows for r in seed_rows]
    df = pd.DataFrame(rows)

    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    df.to_parquet(ARTIFACTS_DIR / "results.parquet", index=False)

    arms = [a.value for a in Arm]
    summary: dict[str, Any] = {
        "n_seeds": N_SEEDS,
        "seeds": SEEDS,
        "n_customers_per_seed": n_customers,
        "elapsed_seconds": None,  # filled at the end
        "headline_comparison": "dobara vs razorpay_default",
        "arms": {arm: _arm_summary(df, arm) for arm in arms},
        "paired_dobara_vs_razorpay_default": _paired_diff(
            df, Arm.DOBARA.value, Arm.RAZORPAY_DEFAULT.value, "net_ltv_total"
        ),
        "paired_aggressive_8x_vs_razorpay_default": _paired_diff(
            df, Arm.AGGRESSIVE_8X.value, Arm.RAZORPAY_DEFAULT.value, "net_ltv_total"
        ),
        # Not the headline (that's dobara vs razorpay_default, the real incumbent) -- this
        # is a structural sanity check with a CI-bearing invariant test attached
        # (tests/test_eval_invariants.py): dobara's candidate space always includes
        # STOP/ABSTAIN with a positivity floor on E[net], so its worst case degenerates to
        # do_nothing's zero-attempt behaviour -- losing to it significantly would be a
        # logical impossibility and always a bug signal, never a finding. A prior run
        # showed do_nothing "beating" dobara; that was traced to a do_nothing
        # arm-construction bug (max_attempts=1, not 0 -- do_nothing was silently making
        # the originally-scheduled debit), fixed 2026-08-25, see docs/DECISIONS.md.
        "paired_dobara_vs_do_nothing": _paired_diff(
            df, Arm.DOBARA.value, Arm.DO_NOTHING.value, "net_ltv_total"
        ),
        "robustness_slices": {
            "note": (
                "Pooled across all 30 seeds' mandate rows for dobara/razorpay_default, "
                "not independently seed-bootstrapped per slice -- see module docstring."
            ),
            "by_bank": {
                "dobara": _slice_recovery_and_net_ltv(df, Arm.DOBARA.value, "bank_id"),
                "razorpay_default": _slice_recovery_and_net_ltv(
                    df, Arm.RAZORPAY_DEFAULT.value, "bank_id"
                ),
            },
            "regime_shift_bank_flag": {
                "dobara": _slice_recovery_and_net_ltv(df, Arm.DOBARA.value, "regime_shift_bank"),
                "razorpay_default": _slice_recovery_and_net_ltv(
                    df, Arm.RAZORPAY_DEFAULT.value, "regime_shift_bank"
                ),
            },
            "by_method": {
                "dobara": _slice_recovery_and_net_ltv(df, Arm.DOBARA.value, "method"),
            },
            "by_first_success_attempt_index": {
                "dobara": _slice_attempt_index(df, Arm.DOBARA.value),
                "razorpay_default": _slice_attempt_index(df, Arm.RAZORPAY_DEFAULT.value),
            },
            "cold_start": {
                "dobara": _slice_recovery_and_net_ltv(df, Arm.DOBARA.value, "is_cold_start"),
                "razorpay_default": _slice_recovery_and_net_ltv(
                    df, Arm.RAZORPAY_DEFAULT.value, "is_cold_start"
                ),
            },
            "outage_windows": {
                "dobara": _slice_outage(df, Arm.DOBARA.value),
                "razorpay_default": _slice_outage(df, Arm.RAZORPAY_DEFAULT.value),
            },
        },
        "permanent_holdout_arm": _holdout_slice(df),
        "credibility_anchor": (
            "Razorpay's own production routing system reports a 4-6% success-rate lift "
            "(https://arxiv.org/abs/2111.00783) across millions of real transactions. "
            "If dobara's headline lift looks far larger than this, treat it as a bug to "
            "investigate, not a result to celebrate -- docs/07-EVAL-SPEC.md."
        ),
    }
    summary["elapsed_seconds"] = round(time.time() - t_start, 1)

    (ARTIFACTS_DIR / "summary.json").write_text(
        json.dumps(_json_safe(summary), indent=2, default=str, allow_nan=False)
    )
    print(f"Wrote {len(df)} rows to artifacts/results.parquet")
    print(f"Wrote artifacts/summary.json in {summary['elapsed_seconds']}s total")

    paired = summary["paired_dobara_vs_razorpay_default"]
    print(
        f"\ndobara - razorpay_default net LTV: {paired['mean_diff']:.2f} "
        f"[{paired['ci_lo']:.2f}, {paired['ci_hi']:.2f}] (significant={paired['significant']})"
    )


if __name__ == "__main__":
    main()
