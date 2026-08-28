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

Per `docs/DECISIONS.md` [2026-08-28] "Post-Session-B follow-ups" and the entry that
supersedes it: naive ancestry ("did any file under a watched directory change") is a
false-positive-prone proxy for "could this artifact's content have changed". Two
mechanisms narrow that proxy, applied in order for every commit that touched a watched
path since an artifact's stamp:

1. Self-regeneration exclusion (automatic, no human judgment). `stamp()` records
   `git_commit` as HEAD's *parent* at write time -- the commit that actually lands the
   write necessarily comes after its own stamp. A commit that rewrites the artifact file
   itself is therefore never "stale relative to itself"; it's evidence the artifact
   already reflects that commit. Any commit in range that touched `path` itself is
   dropped from the stale set before the watched-path check runs.
2. Committed waivers (`docs/artifact_freshness_waivers.json`), for a commit that
   touched a watched path but is known, and written down, not to affect this artifact's
   generation -- e.g. a helper function added to `eval/provenance.py` that no generator
   calls yet. A waiver is scoped to one (artifact, commit) pair and requires a reason;
   it is not a way to narrow `WATCHED_PATHS` and does not apply to any other commit or
   artifact. Default stays fail: an unwaived, non-self-regen touch to a watched path
   fails the gate, which is what catches a real change to `agent/decide.py`'s scoring
   that nobody regenerated artifacts for.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from eval.provenance import content_hash

WATCHED_PATHS = ["agent/", "models/", "eval/", "sim/"]
WAIVERS_PATH = Path("docs/artifact_freshness_waivers.json")

# (artifact path, extra watched paths beyond WATCHED_PATHS above). The ask-why cache is
# derived from agent/'s audit fields *and* from the narration code that turns them into
# prose *and* from artifacts/demo_batch.json itself, whose decisions it narrates -- a
# regeneration of the fixture with different decisions leaves every cached narrative
# describing a decision that no longer exists.
#
# llm/ and scripts/generate_ask_why.py have no bearing on any other artifact here, so
# they're scoped to just this one entry rather than added to the global WATCHED_PATHS
# (which would flag every artifact stale on any llm/ change, including ones with nothing
# to do with narration).
#
# demo_batch.json's dependency on its own generator is checked by ancestry below like
# everything else; its dependency on *what it narrates* being consumed correctly by the
# ask-why cache is a separate, content-hash check -- see HASH_DEPENDENCIES.
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

# (cached artifact, source artifact, hash field in the cached artifact's provenance,
# field of the source artifact that's actually narrated/consumed). Checked by content,
# not commit ancestry -- see the note above ARTIFACTS.
HASH_DEPENDENCIES: list[tuple[Path, Path, str, str]] = [
    (
        Path("artifacts/llm_cache/ask_why.json"),
        Path("artifacts/demo_batch.json"),
        "demo_batch_content_hash",
        "audit_by_mandate",
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


def _commits_touching(path_args: list[str], since: str) -> set[str]:
    out = _run(["log", f"{since}..HEAD", "--format=%H", "--", *path_args])
    return {line for line in out.split() if line}


def _load_waivers() -> set[tuple[str, str]]:
    if not WAIVERS_PATH.exists():
        return set()
    entries = json.loads(WAIVERS_PATH.read_text())
    return {(e["artifact"], e["commit"]) for e in entries}


def stale_commits_for(path: Path, commit: str, watched: list[str]) -> tuple[list[str], list[str]]:
    """Full hashes of commits in `commit..HEAD` that touched `watched`, split into
    (real, waived) after dropping self-regeneration commits (see module docstring)."""
    touching_watched = _commits_touching(watched, since=commit)
    self_regen = _commits_touching([str(path)], since=commit)
    candidates = touching_watched - self_regen
    waivers = _load_waivers()
    real = sorted(c for c in candidates if (str(path), c) not in waivers)
    waived = sorted(c for c in candidates if (str(path), c) in waivers)
    return real, waived


def check_hash_dependency(
    cached_path: Path, source_path: Path, hash_field: str, source_field: str
) -> bool:
    if not cached_path.exists() or not source_path.exists():
        print(f"SKIP  {cached_path} vs {source_path} content hash (not present)")
        return True
    cached_data = json.loads(cached_path.read_text())
    stored_hash = cached_data.get("provenance", {}).get(hash_field)
    if not stored_hash:
        print(f"FAIL  {cached_path}: no provenance.{hash_field} stamp")
        return False
    source_data = json.loads(source_path.read_text())
    current_hash = content_hash(source_data[source_field])
    if current_hash != stored_hash:
        print(
            f"FAIL  {cached_path}: {source_path}'s {source_field!r} content hash "
            f"({current_hash[:12]}) no longer matches what was narrated ({stored_hash[:12]})"
        )
        return False
    print(f"OK    {cached_path}: {source_path}'s {source_field!r} content unchanged")
    return True


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
    real, waived = stale_commits_for(path, commit, watched)
    if waived:
        print(
            f"WAIVE {path}: {len(waived)} commit(s) touched {'/'.join(watched)} but are "
            f"waived (see {WAIVERS_PATH}):"
        )
        for c in waived:
            print(f"        {c[:12]}")
    if real:
        print(
            f"FAIL  {path}: generated at {commit[:12]}, but {len(real)} later "
            f"commit(s) touched {'/'.join(watched)}:"
        )
        for c in real:
            print(f"        {c[:12]} {_run(['log', '-1', '--format=%s', c]).strip()}")
        return False
    print(f"OK    {path}: fresh (generated at {commit[:12]})")
    return True


def main() -> None:
    # A list comprehension, not all(genexpr) -- all() short-circuits on the first False,
    # which silently skipped checking (and printing a result for) every artifact after
    # the first failure. Discovered when a real, unrelated summary.json staleness meant
    # this script never even evaluated whether the newly added ask_why.json was fresh.
    results = [check_one(p, extra) for p, extra in ARTIFACTS]
    results += [
        check_hash_dependency(cached, source, hash_field, source_field)
        for cached, source, hash_field, source_field in HASH_DEPENDENCIES
    ]
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
