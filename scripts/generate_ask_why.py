"""Generates the `/audit` "ask why" narratives, once, offline, and commits the result.

Per the static-export deploy: there is no server on the deployed site, so there is no
runtime to hold an API key or make an LLM call. Every narrative is generated ahead of
time from the structured audit record (never the reverse -- the LLM never sees anything
`agent/decide.py` didn't already compute and log) and cached to
`artifacts/llm_cache/ask_why.json`, which the frontend reads as a plain static asset.
This script is the only thing in the repo that calls an LLM.

Every cache entry is stamped with the provider, model, and timestamp that actually
generated it -- not once at file level. Per docs/DECISIONS.md [2026-08-28]: getting the
full batch through free-tier quotas took several provider/model switches, so the cache
*is* genuinely heterogeneous, the same way `model_versions` is per-decision on every
audit record and every number in this repo carries a source. The stamp is taken live, at
generation time, from the provider object that actually made the call -- never
reconstructed after the fact from logs, which would risk quietly asserting an attribution
that's wrong in a repo whose whole point is that every claim is checkable.

Resumable: re-running only fills in keys missing from the existing cache file, so an
interrupted run (rate limit, network blip) picks back up rather than re-spending calls
on decisions already narrated. A cache entry from before this per-entry-provenance
schema existed (a bare string, not a `{text, provider, model, generated_at}` object) is
treated as absent, not reused -- resumability applies within one schema, not across one.

Usage: GEMINI_API_KEY=... uv run python -m scripts.generate_ask_why
   or: GROQ_API_KEY=...   uv run python -m scripts.generate_ask_why
"""

from __future__ import annotations

import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from api.converters import render_from_decision_out
from api.demo import _decision_out_from_json
from eval.provenance import content_hash, stamp
from llm.narrate import narrate
from llm.provider import QuotaExhausted, default_provider

DEMO_BATCH_PATH = Path("artifacts/demo_batch.json")
CACHE_PATH = Path("artifacts/llm_cache/ask_why.json")

# Groq (GroqProvider, llm/provider.py): a 10-call burst test came back with
# x-ratelimit-remaining-requests decrementing by exactly 1/call from 997 and remaining-
# tokens comfortably in the thousands throughout -- a single generous daily budget, not
# the several small per-model buckets Gemini's free tier split this batch across. 0.5s
# is conservative headroom, not a measured ceiling. Re-runs skip cached keys, so this
# cost is paid once per decision ever.
PAUSE_SECONDS = 0.5


def decision_key(mandate_id: int, cycle_index: int, attempt_index: int) -> str:
    """Identity only -- kept exactly as `web/lib/server-data.ts::getAskWhy()` looks it
    up (`${mandateId}:${cycleIndex}:${attemptIndex}`), a contract this function cannot
    change unilaterally. Staleness under a changed decision (see `main()`'s
    `audit_content_hash` check below) is handled separately, per-entry, not by folding
    content into this key."""
    return f"{mandate_id}:{cycle_index}:{attempt_index}"


def load_cache() -> dict[str, dict[str, Any]]:
    if not CACHE_PATH.exists():
        return {}
    data = json.loads(CACHE_PATH.read_text())
    narratives = data.get("narratives", {})
    assert isinstance(narratives, dict)
    # Legacy bare-string entries (pre-per-entry-provenance) don't carry provider/model --
    # drop them so they're regenerated with the current schema rather than silently kept
    # without an attribution.
    return {k: v for k, v in narratives.items() if isinstance(v, dict) and "text" in v}


def save_cache(narratives: dict[str, dict[str, Any]], audit_by_mandate: dict[str, Any]) -> None:
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    provenance = stamp()
    # Recorded alongside (not instead of) git_commit -- see docs/DECISIONS.md
    # [2026-08-28] and scripts/check_artifact_freshness.py. Lets the freshness gate tell
    # "demo_batch.json's decision content actually changed" apart from "demo_batch.json
    # was rewritten with identical content", which git ancestry alone can't do.
    provenance["demo_batch_content_hash"] = content_hash(audit_by_mandate)
    payload = {
        "narratives": narratives,
        "generated_by": "llm/narrate.py + scripts/generate_ask_why.py, see module docstrings",
        "schema_note": (
            "Each entry carries its own {provider, model, generated_at} -- the cache is "
            "genuinely heterogeneous across free-tier quota switches, see "
            "docs/DECISIONS.md [2026-08-28]."
        ),
        "provenance": provenance,
    }
    CACHE_PATH.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def main() -> None:
    batch = json.loads(DEMO_BATCH_PATH.read_text())
    audit_by_mandate: dict[str, list[dict[str, object]]] = batch["audit_by_mandate"]

    narratives = load_cache()
    provider = default_provider()

    total = sum(len(rows) for rows in audit_by_mandate.values())
    done = 0
    generated = 0
    skipped = 0
    failed: list[str] = []

    for rows in audit_by_mandate.values():
        for raw in rows:
            done += 1
            decision = _decision_out_from_json(raw)
            key = decision_key(decision.mandate_id, decision.cycle_index, decision.attempt_index)
            audit_text = render_from_decision_out(decision)
            audit_digest = content_hash(audit_text)
            cached = narratives.get(key)
            # Bug found and fixed 2026-09-02 (docs/DECISIONS.md [2026-09-02] "Platt
            # adopted"): identity alone doesn't detect a decision whose NUMBERS changed
            # under a model swap (different candidate wins, different expected_net) at
            # the same (mandate, cycle, attempt) -- reusing that stale text produced
            # narratives the grounding gate correctly flagged at scale (897/1,312).
            # `audit_content_hash` (added to every entry from here on; missing on older
            # entries treated as stale, not trusted) makes that regenerate instead of
            # silently reusing the wrong text, while the identity KEY itself stays
            # exactly what web/lib/server-data.ts::getAskWhy() looks up.
            if cached is not None and cached.get("audit_content_hash") == audit_digest:
                skipped += 1
                continue
            try:
                text = narrate(provider, audit_text)
                narratives[key] = {
                    "text": text,
                    "provider": provider.provider_id,
                    "model": provider.model,
                    "generated_at": datetime.now(UTC).isoformat(),
                    "audit_content_hash": audit_digest,
                }
                generated += 1
            except QuotaExhausted as exc:
                # Not transient -- every remaining decision would fail identically, so
                # save what succeeded and stop immediately rather than cascading a FAIL
                # through the other ~1,000+ decisions.
                save_cache(narratives, audit_by_mandate)
                print(f"ABORT at {key}: {exc}", file=sys.stderr)
                print(
                    f"saved {generated} newly generated ({len(narratives)} total cached) "
                    "before stopping.",
                    file=sys.stderr,
                )
                sys.exit(2)
            except Exception as exc:  # noqa: BLE001 -- log and continue; resumable by design
                failed.append(key)
                print(f"FAIL  {key}: {exc}", file=sys.stderr)
                continue
            if generated % 25 == 0:
                save_cache(narratives, audit_by_mandate)
                print(f"[{done}/{total}] checkpoint saved ({generated} generated this run)")
            time.sleep(PAUSE_SECONDS)

    save_cache(narratives, audit_by_mandate)
    print(
        f"done: {generated} generated, {skipped} already cached, {len(failed)} failed "
        f"(of {total} total decisions)"
    )
    if failed:
        print(f"failed keys: {failed}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
