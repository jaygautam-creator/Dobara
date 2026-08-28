"""Generates the `/audit` "ask why" narratives, once, offline, and commits the result.

Per the static-export deploy: there is no server on the deployed site, so there is no
runtime to hold an API key or make an LLM call. Every narrative is generated ahead of
time from the structured audit record (never the reverse -- the LLM never sees anything
`agent/decide.py` didn't already compute and log) and cached to
`artifacts/llm_cache/ask_why.json`, which the frontend reads as a plain static asset.
This script is the only thing in the repo that calls an LLM.

Resumable: re-running only fills in keys missing from the existing cache file, so an
interrupted run (rate limit, network blip) picks back up rather than re-spending calls
on decisions already narrated.

Usage: GEMINI_API_KEY=... uv run python -m scripts.generate_ask_why
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from api.converters import render_from_decision_out
from api.demo import _decision_out_from_json
from eval.provenance import stamp
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
    return f"{mandate_id}:{cycle_index}:{attempt_index}"


def load_cache() -> dict[str, str]:
    if not CACHE_PATH.exists():
        return {}
    data = json.loads(CACHE_PATH.read_text())
    narratives = data.get("narratives", {})
    assert isinstance(narratives, dict)
    return narratives


def save_cache(narratives: dict[str, str]) -> None:
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "narratives": narratives,
        "generated_by": "llm/narrate.py + scripts/generate_ask_why.py, see module docstrings",
        "provenance": stamp(),
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
            if key in narratives:
                skipped += 1
                continue
            audit_text = render_from_decision_out(decision)
            try:
                narratives[key] = narrate(provider, audit_text)
                generated += 1
            except QuotaExhausted as exc:
                # Not transient -- every remaining decision would fail identically, so
                # save what succeeded and stop immediately rather than cascading a FAIL
                # through the other ~1,000+ decisions.
                save_cache(narratives)
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
                save_cache(narratives)
                print(f"[{done}/{total}] checkpoint saved ({generated} generated this run)")
            time.sleep(PAUSE_SECONDS)

    save_cache(narratives)
    print(
        f"done: {generated} generated, {skipped} already cached, {len(failed)} failed "
        f"(of {total} total decisions)"
    )
    if failed:
        print(f"failed keys: {failed}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
