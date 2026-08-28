"""Covers scripts/check_artifact_freshness.py's own correctness -- per
docs/DECISIONS.md [2026-08-28] "Post-Session-B follow-ups" (and its correction), this
gate has produced two false positives already and had no test of its own. Builds a
throwaway git repo so commits can actually be made and inspected; the real repo's
history is never touched.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from scripts.check_artifact_freshness import stale_commits_for


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, check=True)
    return result.stdout


@pytest.fixture
def scratch_repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "test")
    (repo / "agent").mkdir()
    (repo / "artifacts").mkdir()
    (repo / "agent" / "decide.py").write_text("SCORE_WEIGHT = 1\n")
    (repo / "artifacts" / "summary.json").write_text(
        json.dumps({"provenance": {"git_commit": "placeholder"}})
    )
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "initial")
    monkeypatch.chdir(repo)
    return repo


def test_real_scoring_change_is_stale(scratch_repo: Path) -> None:
    stamp_commit = _git(scratch_repo, "rev-parse", "HEAD").strip()

    (scratch_repo / "agent" / "decide.py").write_text("SCORE_WEIGHT = 2\n")
    _git(scratch_repo, "add", "-A")
    _git(scratch_repo, "commit", "-q", "-m", "change scoring weight")

    real, waived = stale_commits_for(Path("artifacts/summary.json"), stamp_commit, ["agent/"])
    assert len(real) == 1
    assert waived == []


def test_self_regeneration_is_not_stale(scratch_repo: Path) -> None:
    stamp_commit = _git(scratch_repo, "rev-parse", "HEAD").strip()

    # A commit that rewrites the artifact itself (e.g. a regen that also happens to
    # touch a watched path via its own provenance stamp) must not flag itself stale.
    (scratch_repo / "artifacts" / "summary.json").write_text(
        json.dumps({"provenance": {"git_commit": stamp_commit}})
    )
    _git(scratch_repo, "add", "-A")
    _git(scratch_repo, "commit", "-q", "-m", "regenerate summary.json")

    real, waived = stale_commits_for(Path("artifacts/summary.json"), stamp_commit, ["agent/"])
    assert real == []
    assert waived == []


def test_waived_commit_is_not_real_stale(scratch_repo: Path) -> None:
    stamp_commit = _git(scratch_repo, "rev-parse", "HEAD").strip()

    (scratch_repo / "agent" / "decide.py").write_text("SCORE_WEIGHT = 2\n")
    _git(scratch_repo, "add", "-A")
    _git(scratch_repo, "commit", "-q", "-m", "unrelated helper, provably inert")
    stale_commit = _git(scratch_repo, "rev-parse", "HEAD").strip()

    waivers_path = scratch_repo / "docs"
    waivers_path.mkdir()
    (waivers_path / "artifact_freshness_waivers.json").write_text(
        json.dumps(
            [
                {
                    "artifact": "artifacts/summary.json",
                    "commit": stale_commit,
                    "reason": "test waiver",
                }
            ]
        )
    )

    import scripts.check_artifact_freshness as gate

    original = gate.WAIVERS_PATH
    gate.WAIVERS_PATH = Path("docs/artifact_freshness_waivers.json")
    try:
        real, waived = stale_commits_for(Path("artifacts/summary.json"), stamp_commit, ["agent/"])
    finally:
        gate.WAIVERS_PATH = original

    assert real == []
    assert waived == [stale_commit]
