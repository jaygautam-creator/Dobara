"""`make check` gate: fails when a committed evidence artifact is older than the code
that generates it. Per `docs/DECISIONS.md` [2026-08-27]: `artifacts/summary.json`
recorded a headline number from a `dobara` policy that four later commits to
`agent/decide.py` had since changed, unnoticed, because nothing in the artifact recorded
which commit produced it. `eval/provenance.py::stamp()` writes `git_commit` into every
evidence artifact; this script checks it against `git log`.

An artifact whose `git_commit` is not an ancestor of `HEAD` (e.g. a local commit not yet
on the branch this checkout has, or a rebase) is reported as unverifiable, not stale --
the check only fails on the case it exists to catch: real, landed commits to the money
path since the artifact was generated.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

WATCHED_PATHS = ["agent/", "models/", "eval/", "sim/"]

# (artifact path, extra watched paths beyond WATCHED_PATHS above). The ask-why cache is
# derived from agent/'s audit fields *and* from the narration code that turns them into
# prose -- a change to either should mark it stale, but llm/ and scripts/generate_ask_why.py
# have no bearing on any other artifact here, so they're scoped to just this one entry
# rather than added to the global WATCHED_PATHS (which would flag every artifact stale on
# any llm/ change, including ones with nothing to do with narration).
ARTIFACTS: list[tuple[Path, list[str]]] = [
    (Path("artifacts/summary.json"), []),
    (Path("artifacts/sensitivity.json"), []),
    (Path("artifacts/demo_batch.json"), []),
    (Path("artifacts/money_chart_data.json"), []),
    (
        Path("artifacts/llm_cache/ask_why.json"),
        ["llm/", "scripts/generate_ask_why.py"],
    ),
]


def _run(args: list[str]) -> str:
    result = subprocess.run(["git", *args], capture_output=True, text=True, check=True)
    return result.stdout


def _is_ancestor(commit: str) -> bool:
    result = subprocess.run(
        ["git", "merge-base", "--is-ancestor", commit, "HEAD"], capture_output=True
    )
    return result.returncode == 0


def check_one(path: Path, extra_watched: list[str]) -> bool:
    if not path.exists():
        print(f"SKIP  {path} (not present)")
        return True
    data = json.loads(path.read_text())
    commit = data.get("provenance", {}).get("git_commit")
    if not commit:
        print(f"FAIL  {path}: no provenance.git_commit stamp")
        return False
    if not _is_ancestor(commit):
        print(
            f"WARN  {path}: git_commit {commit[:12]} is not an ancestor of HEAD -- "
            f"unverifiable (local/rebased history), not treated as stale"
        )
        return True
    watched = [*WATCHED_PATHS, *extra_watched]
    later = _run(["log", f"{commit}..HEAD", "--oneline", "--", *watched]).strip()
    if later:
        stale_commits = later.splitlines()
        print(
            f"FAIL  {path}: generated at {commit[:12]}, but {len(stale_commits)} later "
            f"commit(s) touched {'/'.join(watched)}:"
        )
        for line in stale_commits:
            print(f"        {line}")
        return False
    print(f"OK    {path}: fresh (generated at {commit[:12]})")
    return True


def main() -> None:
    # A list comprehension, not all(genexpr) -- all() short-circuits on the first False,
    # which silently skipped checking (and printing a result for) every artifact after
    # the first failure. Discovered when a real, unrelated summary.json staleness meant
    # this script never even evaluated whether the newly added ask_why.json was fresh.
    results = [check_one(p, extra) for p, extra in ARTIFACTS]
    ok = all(results)
    if not ok:
        print(
            "\nOne or more evidence artifacts are stale relative to agent/models/eval/sim "
            "(or, for the ask-why cache, llm/). Regenerate with `make eval`, `python -m "
            "eval.sensitivity`, `make demo-fixture`, `make money-chart`, and/or "
            "`make ask-why` before committing."
        )
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
