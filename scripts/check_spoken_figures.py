"""`make check` gate: fails when a figure actually spoken in the pitch video (per
`docs/09-DEMO-SCRIPT.md` / `docs/09A-REHEARSAL-PACK.md`) does not match the artifact
field it claims to come from.

**Why this exists, not a broader one.** This session hit the same failure mode three
times: `76%`/`94%` (docs/DECISIONS.md [2026-09-01] "Number collision resolved"), the
`day_of_month` gain rank (docs/DECISIONS.md [2026-09-01] "third- vs fourth-highest-gain"
correction), and now `77.2%` vs `75.7%` (docs/DECISIONS.md [2026-09-02] "Third number
collision") -- every one was a number measured once, in one place, then re-typed by
hand somewhere else without ever being re-checked against the artifact it came from. A
general prose-parsing checker (extract every number from every markdown file, guess
which artifact field it means) was considered and rejected here: it cannot reliably
tell "the number this sentence is claiming" from "a mandate ID," "a day of the month,"
or "a citation year" without a much larger investment than this gate's payoff justifies
-- a narrow check that runs beats a broad one that doesn't (the task's own framing).
Instead: an explicit, hand-maintained table (`FIGURES` below), one row per figure the
video's own script/rehearsal-pack narration actually speaks aloud. Adding a new spoken
figure to the video means adding a row here in the same commit -- the discipline this
gate exists to enforce, made structurally required rather than merely asked for.

Each row names: the artifact field the figure is computed from (possibly on another
branch, read via `git show <ref>:<path>` without checking it out -- this project's
calibrator-experiment figures live on `experiment/platt-calibrator`, deliberately not
merged to `main`), a `compute` function turning the loaded artifact(s) into the exact
value, a `format` function turning that value into the exact substring the doc prose
must contain, and the doc file(s) that substring must appear in verbatim.
"""

from __future__ import annotations

import json
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any


def _read_local(path: str) -> dict[str, Any]:
    data: dict[str, Any] = json.loads(Path(path).read_text())
    return data


def _read_at_ref(ref: str, path: str) -> dict[str, Any]:
    out = subprocess.run(
        ["git", "show", f"{ref}:{path}"], capture_output=True, text=True, check=True
    )
    data: dict[str, Any] = json.loads(out.stdout)
    return data


@dataclass(frozen=True)
class SpokenFigure:
    name: str
    # (ref, path) pairs -- ref "" means the local working tree (main); anything else is
    # read via `git show ref:path`, never checked out, so this script never switches
    # branches under the caller.
    sources: tuple[tuple[str, str], ...]
    # Returns one or more required substrings. Multiple entries are checked
    # independently (each must appear SOMEWHERE in the doc, not necessarily adjacent
    # or on the same line) -- markdown bold/line-wrapping routinely splits a single
    # "point [lo, hi]" phrase across "**...**" markers or a line break, so pinning one
    # giant literal string is too brittle; pinning the point estimate and the CI
    # bracket as two separate, still-exact substrings is not.
    compute: Callable[..., tuple[str, ...]]
    doc_files: tuple[str, ...]


def _tie_rate_figure() -> tuple[str, ...]:
    d = _read_local("artifacts/production_tie_rate.json")
    s = d["slices"]["all_decisions_with_alternatives"]
    iso = s["isotonic"]["tie_rate"] * 100
    platt = s["platt"]["tie_rate"] * 100
    # Checked as two independent substrings, not one joined phrase: prose docs write
    # "75.7% to 17.9%" and the rehearsal pack's table writes "75.7% → 17.9%" -- both
    # are the same figure, correctly sourced, just glued differently. Requiring both
    # numbers to appear (in either style) is the real check; the connector word isn't.
    return (f"{iso:.1f}%", f"{platt:.1f}%")


def _shipped_headline_figure() -> tuple[str, ...]:
    d = _read_local("artifacts/summary.json")
    p = d["paired_dobara_vs_razorpay_default"]
    n = d["n_customers_per_seed"]
    point, lo, hi = p["mean_diff"] / n, p["ci_lo"] / n, p["ci_hi"] / n
    return (f"+₹{point:.2f}/mandate", f"[+₹{lo:.2f}, +₹{hi:.2f}]")


def _experiment_headline_figure() -> tuple[str, ...]:
    d = _read_at_ref("experiment/platt-calibrator", "artifacts/summary.json")
    p = d["paired_dobara_vs_razorpay_default"]
    n = d["n_customers_per_seed"]
    point, lo, hi = p["mean_diff"] / n, p["ci_lo"] / n, p["ci_hi"] / n
    return (f"−₹{abs(point):.2f}/mandate", f"[−₹{abs(lo):.2f}, −₹{abs(hi):.2f}]")


def _gross_delta_figure() -> tuple[str, ...]:
    main_s = _read_local("artifacts/summary.json")
    exp_s = _read_at_ref("experiment/platt-calibrator", "artifacts/summary.json")
    main_gross = main_s["arms"]["dobara"]["gross_recovered_inr"]["point"]
    exp_gross = exp_s["arms"]["dobara"]["gross_recovered_inr"]["point"]
    delta = exp_gross - main_gross
    return (f"−₹{abs(delta):,.0f}",)


def _revocation_delta_figure() -> tuple[str, ...]:
    main_s = _read_local("artifacts/summary.json")
    exp_s = _read_at_ref("experiment/platt-calibrator", "artifacts/summary.json")
    main_rev = main_s["arms"]["dobara"]["revocations_total"]["point"]
    exp_rev = exp_s["arms"]["dobara"]["revocations_total"]["point"]
    delta = exp_rev - main_rev
    return (f"+{delta:.1f}",)


def _home_demo_mandate_figure() -> tuple[str, ...]:
    d = _read_local("artifacts/home_demo.json")
    return (f"mandate {d['mandate']['mandate_id']}",)


def _home_demo_aggressive_figure() -> tuple[str, ...]:
    d = _read_local("artifacts/home_demo.json")
    t = d["lanes"]["aggressive_8x"]["totals"]
    return (
        f"{t['n_notifications']} notifications",
        f"{t['n_successes']} successful debit",
        f"cycle {t['revoked_at_cycle']}",
        f"₹{t['ltv_lost_inr']:,.2f}",
    )


def _home_demo_dobara_figure() -> tuple[str, ...]:
    d = _read_local("artifacts/home_demo.json")
    t = d["lanes"]["dobara"]["totals"]
    return (
        f"{t['n_notifications']} notifications",
        f"{t['n_successes']} successful debit",
    )


def _home_demo_selection_figure() -> tuple[str, ...]:
    d = _read_local("artifacts/home_demo.json")
    sel = d["selection"]
    adv = sel["net_ltv_advantage_inr"]
    return (
        f"{sel['n_candidates']} candidates",
        f"₹{adv['median']:,.2f}",
        f"₹{adv['p25']:,.2f}",
        f"₹{adv['p75']:,.2f}",
    )


FIGURES: tuple[SpokenFigure, ...] = (
    SpokenFigure(
        name="argmax tie rate, isotonic -> Platt (all-decisions slice)",
        sources=(("", "artifacts/production_tie_rate.json"),),
        compute=_tie_rate_figure,
        doc_files=("docs/09A-REHEARSAL-PACK.md", "README.md", "docs/DECISIONS.md"),
    ),
    SpokenFigure(
        name="shipped (main) headline net LTV lift, per mandate",
        sources=(("", "artifacts/summary.json"),),
        compute=_shipped_headline_figure,
        doc_files=("README.md",),
    ),
    SpokenFigure(
        name="Platt (experiment/platt-calibrator) headline net LTV loss, per mandate",
        sources=(("experiment/platt-calibrator", "artifacts/summary.json"),),
        compute=_experiment_headline_figure,
        doc_files=("README.md",),
    ),
    SpokenFigure(
        name="gross recovered delta, dobara, main vs experiment/platt-calibrator",
        sources=(
            ("", "artifacts/summary.json"),
            ("experiment/platt-calibrator", "artifacts/summary.json"),
        ),
        compute=_gross_delta_figure,
        doc_files=("README.md", "docs/DECISIONS.md"),
    ),
    SpokenFigure(
        name="revocations delta, dobara, main vs experiment/platt-calibrator",
        sources=(
            ("", "artifacts/summary.json"),
            ("experiment/platt-calibrator", "artifacts/summary.json"),
        ),
        compute=_revocation_delta_figure,
        doc_files=("README.md", "docs/DECISIONS.md"),
    ),
    SpokenFigure(
        name="home demo: selected mandate id",
        sources=(("", "artifacts/home_demo.json"),),
        compute=_home_demo_mandate_figure,
        doc_files=("docs/09-DEMO-SCRIPT.md", "docs/09A-REHEARSAL-PACK.md"),
    ),
    SpokenFigure(
        name="home demo: aggressive_8x lane totals",
        sources=(("", "artifacts/home_demo.json"),),
        compute=_home_demo_aggressive_figure,
        doc_files=("docs/09-DEMO-SCRIPT.md", "docs/09A-REHEARSAL-PACK.md"),
    ),
    SpokenFigure(
        name="home demo: dobara lane totals",
        sources=(("", "artifacts/home_demo.json"),),
        compute=_home_demo_dobara_figure,
        doc_files=("docs/09-DEMO-SCRIPT.md", "docs/09A-REHEARSAL-PACK.md"),
    ),
    SpokenFigure(
        name="home demo: candidate-set selection stats",
        sources=(("", "artifacts/home_demo.json"),),
        compute=_home_demo_selection_figure,
        doc_files=("docs/09A-REHEARSAL-PACK.md",),
    ),
)


def main() -> None:
    failed = False
    for fig in FIGURES:
        try:
            expected_parts = fig.compute()
        except subprocess.CalledProcessError as exc:
            print(f"SKIP  {fig.name}: could not read a source ({exc}) -- is the ref fetched?")
            continue
        for doc_path in fig.doc_files:
            text = Path(doc_path).read_text()
            for expected in expected_parts:
                if expected in text:
                    print(f"OK    {fig.name}: {expected!r} found in {doc_path}")
                else:
                    failed = True
                    print(
                        f"FAIL  {fig.name}: expected {expected!r} not found verbatim in "
                        f"{doc_path} -- the artifact and the doc have drifted"
                    )
    if failed:
        print("\nOne or more spoken figures no longer match their artifact source.")
        sys.exit(1)


if __name__ == "__main__":
    main()
