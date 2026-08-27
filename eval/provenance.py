"""Provenance stamping for evidence artifacts (`artifacts/summary.json`,
`sensitivity.json`, `demo_batch.json`). Per `docs/DECISIONS.md` [2026-08-27]: a headline
number survived four commits of `agent/decide.py` changing underneath it, unnoticed,
because nothing in the artifact recorded which code produced it. Every writer of a
committed evidence artifact must call `stamp()` and merge its result into the JSON's
top-level `provenance` key -- `scripts/check_artifact_freshness.py` (run by `make check`)
enforces that this key exists and that no later commit touching `agent/`, `models/`,
`eval/`, or `sim/` has landed since.
"""

from __future__ import annotations

import subprocess
from datetime import UTC, datetime
from typing import Any


def _git_commit() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True
    )
    return result.stdout.strip()


def stamp() -> dict[str, Any]:
    """`{"generated_at": <UTC ISO 8601>, "git_commit": <full SHA of HEAD at write time>}`
    -- called at the point a run's output is about to be written, not at process start,
    so it reflects the code that actually produced the numbers."""
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "git_commit": _git_commit(),
    }
