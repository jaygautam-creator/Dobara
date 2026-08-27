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

ARTIFACTS = [
    Path("artifacts/summary.json"),
    Path("artifacts/sensitivity.json"),
    Path("artifacts/demo_batch.json"),
]
WATCHED_PATHS = ["agent/", "models/", "eval/", "sim/"]


def _run(args: list[str]) -> str:
    result = subprocess.run(["git", *args], capture_output=True, text=True, check=True)
    return result.stdout


def _is_ancestor(commit: str) -> bool:
    result = subprocess.run(
        ["git", "merge-base", "--is-ancestor", commit, "HEAD"], capture_output=True
    )
    return result.returncode == 0


def check_one(path: Path) -> bool:
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
    later = _run(["log", f"{commit}..HEAD", "--oneline", "--", *WATCHED_PATHS]).strip()
    if later:
        stale_commits = later.splitlines()
        print(
            f"FAIL  {path}: generated at {commit[:12]}, but {len(stale_commits)} later "
            f"commit(s) touched {'/'.join(WATCHED_PATHS)}:"
        )
        for line in stale_commits:
            print(f"        {line}")
        return False
    print(f"OK    {path}: fresh (generated at {commit[:12]})")
    return True


def main() -> None:
    ok = all(check_one(p) for p in ARTIFACTS)
    if not ok:
        print(
            "\nOne or more evidence artifacts are stale relative to agent/models/eval/sim. "
            "Regenerate with `make eval`, `python -m eval.sensitivity`, and/or "
            "`make demo-fixture` before committing."
        )
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
