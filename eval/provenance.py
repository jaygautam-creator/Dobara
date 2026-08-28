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

import hashlib
import json
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


def content_hash(value: Any) -> str:
    """SHA-256 of `value`'s canonical JSON encoding. Per `docs/DECISIONS.md`
    [2026-08-28]: `git_commit` ancestry alone can't tell a commit that regenerated an
    artifact with byte-identical content from one that actually changed it -- the commit
    that writes the artifact necessarily post-dates the commit `stamp()` records, so a
    provenance stamp can never satisfy an ancestry check against its own commit. A
    content hash of the fields that are actually consumed downstream lets a freshness
    check compare what changed instead of when it landed."""
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()
