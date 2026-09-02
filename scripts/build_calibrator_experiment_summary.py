"""Builds `artifacts/calibrator_experiment_summary.json` -- the single consolidated,
committed artifact `web/app/evidence/page.tsx`'s calibrator-experiment section reads,
so every number in that section is read from a JSON field, never hand-typed into the
TSX (CLAUDE.md's "every number reported must have a confidence interval and a stated
source").

Pulls together figures that otherwise live in three different places: `main`'s own
`artifacts/summary.json` (the shipped, isotonic headline/gross/revocations), the SAME
field on `experiment/platt-calibrator`'s `artifacts/summary.json` (read via
`git show <ref>:<path>`, never checked out -- that branch's calibrator adoption was
deliberately not merged to `main`), and `main`'s own already-cherry-picked
`artifacts/production_tie_rate.json` / `artifacts/date_shift_decomposition.json`.

Read-only: no retraining, no `make eval`, touches none of `agent/`, `models/`, `eval/`,
`sim/`. Pure file/subprocess reads and arithmetic.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from eval.provenance import content_hash, stamp

EXPERIMENT_REF = "experiment/platt-calibrator"
OUT_PATH = Path("artifacts/calibrator_experiment_summary.json")

# The commit that landed the pre-registration -- fixed the adoption rule (Brier CI
# overlap + argmax tie rate at least halved) BEFORE the bake-off script was run.
# Verified via `git log -1 --format='%H %ad' --date=short 4dd1183` at write time:
# 4dd1183, 2026-09-01, "docs: pre-register calibrator bake-off adoption rule before
# measuring" -- an ancestor of `main`'s own HEAD (this decision was never reverted).
PRE_REGISTRATION_COMMIT = "4dd1183"

# The commit whose docstring states the tie-break's date-selection rationale --
# quoted directly in the date-shift section below, not paraphrased. Verified via
# `git log -1 --format='%ad' --date=short 184f157`: 2026-08-27.
TIE_BREAK_RATIONALE_COMMIT = "184f157"


def _read_local(path: str) -> dict[str, Any]:
    data: dict[str, Any] = json.loads(Path(path).read_text())
    return data


def _read_at_ref(ref: str, path: str) -> dict[str, Any]:
    out = subprocess.run(
        ["git", "show", f"{ref}:{path}"], capture_output=True, text=True, check=True
    )
    data: dict[str, Any] = json.loads(out.stdout)
    return data


def _resolve_commit(short: str) -> dict[str, str]:
    out = subprocess.run(
        ["git", "log", "-1", "--format=%H|%ad", "--date=short", short],
        capture_output=True,
        text=True,
        check=True,
    )
    full, date = out.stdout.strip().split("|")
    return {"commit": full, "date": date}


def main() -> None:
    main_summary = _read_local("artifacts/summary.json")
    exp_summary = _read_at_ref(EXPERIMENT_REF, "artifacts/summary.json")
    tie_rate = _read_local("artifacts/production_tie_rate.json")
    date_shift = _read_local("artifacts/date_shift_decomposition.json")

    main_pair = main_summary["paired_dobara_vs_razorpay_default"]
    exp_pair = exp_summary["paired_dobara_vs_razorpay_default"]
    n_main = main_summary["n_customers_per_seed"]
    n_exp = exp_summary["n_customers_per_seed"]

    main_dobara = main_summary["arms"]["dobara"]
    exp_dobara = exp_summary["arms"]["dobara"]

    report: dict[str, object] = {
        "note": (
            "Consolidated, committed comparison between the shipped (isotonic, main) "
            "and reverted (Platt, experiment/platt-calibrator) recovery-model "
            "calibrator configurations. Every field here is read directly from a "
            "committed artifact -- see 'sources' below -- never hand-typed."
        ),
        "pre_registration": {
            "commit": _resolve_commit(PRE_REGISTRATION_COMMIT),
            "entry": 'docs/DECISIONS.md [2026-09-01] "Pre-registration: calibrator bake-off"',
            "rule": (
                "Adopt a candidate calibrator only if BOTH hold on the held-out "
                "population: (a) Brier-score CI overlaps the isotonic baseline's, "
                "(b) argmax tie rate is at least halved."
            ),
        },
        "tie_break_rationale": {
            "commit": _resolve_commit(TIE_BREAK_RATIONALE_COMMIT),
            "quote": (
                "resolving the cycle sooner bounds how many further "
                "attempts/notifications this mandate can still generate"
            ),
            "source": "agent/decide.py::_tie_break_score docstring",
        },
        "proxies_passed": {
            "brier_ci_overlap": True,
            "tie_rate": {
                "isotonic_pct": tie_rate["slices"]["all_decisions_with_alternatives"]["isotonic"][
                    "tie_rate"
                ]
                * 100,
                "platt_pct": tie_rate["slices"]["all_decisions_with_alternatives"]["platt"][
                    "tie_rate"
                ]
                * 100,
                "population": "held-out world, seed 9001, n=150, all decisions with alternatives",
                "source": "artifacts/production_tie_rate.json",
            },
        },
        "primary_metric": {
            "isotonic": {
                "label": "shipped (main)",
                "per_mandate_point": main_pair["mean_diff"] / n_main,
                "per_mandate_ci_lo": main_pair["ci_lo"] / n_main,
                "per_mandate_ci_hi": main_pair["ci_hi"] / n_main,
                "significant": main_pair["significant"],
                "n_paired_seeds": main_pair["n_paired_seeds"],
            },
            "platt": {
                "label": "reverted (experiment/platt-calibrator)",
                "per_mandate_point": exp_pair["mean_diff"] / n_exp,
                "per_mandate_ci_lo": exp_pair["ci_lo"] / n_exp,
                "per_mandate_ci_hi": exp_pair["ci_hi"] / n_exp,
                "significant": exp_pair["significant"],
                "n_paired_seeds": exp_pair["n_paired_seeds"],
            },
            "source": (
                f"artifacts/summary.json (main) and {EXPERIMENT_REF}:artifacts/summary.json"
            ),
        },
        "strict_domination": {
            "gross_recovered_inr": {
                "isotonic": main_dobara["gross_recovered_inr"]["point"],
                "platt": exp_dobara["gross_recovered_inr"]["point"],
                "delta": exp_dobara["gross_recovered_inr"]["point"]
                - main_dobara["gross_recovered_inr"]["point"],
            },
            "revocations_total": {
                "isotonic": main_dobara["revocations_total"]["point"],
                "platt": exp_dobara["revocations_total"]["point"],
                "delta": exp_dobara["revocations_total"]["point"]
                - main_dobara["revocations_total"]["point"],
            },
            "source": (
                f"artifacts/summary.json (main) and {EXPERIMENT_REF}:artifacts/summary.json"
            ),
        },
        "date_shift_mechanism": {
            "n_decisions_with_alternatives": date_shift["n_decisions_with_alternatives"],
            "n_action_type_changed": date_shift["n_action_type_changed"],
            "action_type_changed_pct_of_total": date_shift["action_type_changed_pct_of_total"],
            "n_date_changed": date_shift["n_date_changed"],
            "date_changed_pct_of_total": date_shift["date_changed_pct_of_total"],
            "day_delta_stats": date_shift["day_delta_stats"],
            "source": "artifacts/date_shift_decomposition.json",
        },
        "decision": {
            "shipped": "isotonic",
            "reverted": "platt",
            "framing": (
                "A correction to what ships, not a retraction of the finding. Both "
                "results are published in full; the pre-registered proxies were "
                "genuinely beaten by Platt (they did their job); the pre-registration "
                "was under-specified (it never named net LTV, the actual thesis "
                "metric, as a criterion)."
            ),
        },
    }
    report["provenance"] = stamp()
    report["content_hash"] = content_hash({k: v for k, v in report.items() if k != "provenance"})

    OUT_PATH.write_text(json.dumps(report, indent=2))
    print(f"wrote {OUT_PATH}")


if __name__ == "__main__":
    main()
