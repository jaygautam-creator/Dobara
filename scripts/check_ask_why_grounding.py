"""`make check` gate: every numeric token in every cached `/audit` "ask why" narrative
must trace back to a number actually present in that decision's structured audit record
(`agent/audit.py::render_fields`'s SAW/THOUGHT/ALT/GATE/DID/WHY text). The prompt
(`llm/narrate.py`) instructs the model not to invent numbers, but an instruction is not a
guarantee -- this is the check that makes it one, over the whole committed cache, not a
sample.

**The risk this exists for**: a narrative stating a rupee figure, probability, or count
that isn't actually in the record it claims to explain. One hallucinated number found by
a judge, in a repo whose central claim is that every statement is auditable, costs more
than the "ask why" feature returns. This script is how that risk gets checked
mechanically instead of trusted on the strength of the prompt.

**Matching, not exact string equality** -- the same rupee figure legitimately appears
differently in prose than in the record (`419.24` in the record vs `Rs.419` rounded in
the narrative; `0.865` as a raw probability vs `86.5%` as a percentage; `1,049` with a
comma vs `1049` without). A narrative number is accepted if it matches some record number
at 0, 1, or 2 decimal places of rounding, or matches a record probability's ×100
percentage form at the same precisions.

**Whitelisting** exists for exactly one purpose: a number the model is allowed to state
that is not literally present in this decision's record because it's evaluator-added
context. Add entries to `WHITELISTED_TOKENS` one at a time, each with a comment naming
the specific narrative and why -- never by loosening `_matches()`'s tolerance to make
unrelated failures disappear.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from api.converters import render_from_decision_out
from api.demo import _decision_out_from_json

CACHE_PATH = Path("artifacts/llm_cache/ask_why.json")
DEMO_BATCH_PATH = Path("artifacts/demo_batch.json")

# (?<!\d) -- a leading "-" only counts as a minus sign when it's not immediately preceded
# by another digit. Without this, an ISO date/time in the audit record ("2026-01-25")
# gets misread as the negative numbers -01 and -25 (the ground truth for day-of-month 25
# becomes -25, which never matches a narrative's literal "25") -- found on the first real
# run against 50 narratives: 28 flagged, 40 unmatched tokens, every single one a
# miscounted calendar day. Not a hallucination signal; a bug in this extractor, fixed
# here rather than papered over with a whitelist entry per affected decision.
_NUMBER = re.compile(r"(?<!\d)-?\d[\d,]*\.?\d*")
_PRECISIONS = (0, 1, 2)

# Each entry reviewed individually against its decision's audit record before being
# added -- see the module docstring's warning against loosening the matcher instead.
# Found on the first full-corpus run (1,296 narratives, 22 flagged): every clause in
# the compliance gate is real domain content the narrative is allowed to name even
# though its *number* isn't literally printed in the record -- RBI-PDN-24H is the
# 24-hour pre-debit notice rule, RBI-AFA-15K is the ₹15,000 additional-factor-
# authentication threshold. A narrative correctly citing "the 24-hour rule" or "the
# ₹15,000 threshold" is reading the clause ID, not inventing a number.
WHITELISTED_TOKENS: set[tuple[str, float]] = {
    # RBI-PDN-24H ("24-hour pre-debit notice") named in prose, not a fabricated count.
    ("18:5:1", 24.0),
    ("78:2:1", 24.0),
    ("112:7:1", 24.0),
    # RBI-AFA-15K (₹15,000 additional-factor-authentication threshold) named in prose.
    ("83:8:1", 15000.0),
    ("96:5:1", 15000.0),
    ("40:8:3", 15000.0),
    # 103:5:2: record's 95% CI lower bound is -13.92 (Rs.-13.92); narrative correctly
    # states this as "losing Rs.13.92" -- the sign is carried by "losing", not by a
    # minus sign in the narrative's own number, so the raw token doesn't match negative
    # ground truth under this checker's sign-preserving comparison. Verified by hand:
    # the underlying claim (possible loss of Rs.13.92) is accurate.
    ("103:5:2", 13.92),
    # 24:6:1: record's largest rejected-alternative delta is Rs.909.45 below the chosen
    # candidate's Rs.909.45 E[net]; narrative paraphrases this loosely as "up to over
    # Rs.900" rather than the exact figure. Directionally and numerically consistent
    # with the record, just not an exact-token match.
    ("24:6:1", 900.0),
}


def extract_numbers(text: str) -> list[float]:
    out = []
    for m in _NUMBER.finditer(text):
        raw = m.group().replace(",", "")
        try:
            out.append(float(raw))
        except ValueError:
            continue
    return out


def acceptable_roundings(
    ground_truth: list[float], total_candidates: int | None = None
) -> set[tuple[int, float]]:
    """Every ground-truth number, rounded to each precision in `_PRECISIONS`, plus two
    principled derived forms -- found on the first real run, added as narrow, explained
    rules, never by loosening the rounding tolerance itself:

    - For anything that looks like a raw probability (strictly between 0 and 1): the same
      roundings of its ×100 percentage form (`0.865` in the record, `86.5%` in prose).
    - `total_candidates - 1`, if given: the record's WHY line states "the best of N
      candidates considered" (the chosen candidate included); a narrative correctly
      paraphrasing this as "N-1 other options" is doing accurate arithmetic on a record
      number, not inventing one (found via 4:3:1: record says "best of 14 candidates",
      narrative said "13 other possible retry options" -- 14-1=13, correct). Scoped to
      this one specific count rather than applied to every whole number in the record --
      audit records are full of small unrelated integers (mandate/cycle/attempt indices,
      notification counts, tie-group sizes), and accepting N-1 for all of them would
      mask a genuinely wrong count that happened to collide with one by coincidence.
    """
    acc: set[tuple[int, float]] = set()
    for v in ground_truth:
        for p in _PRECISIONS:
            acc.add((p, round(v, p)))
        if 0 < v < 1:
            pct = v * 100
            for p in _PRECISIONS:
                acc.add((p, round(pct, p)))
    if total_candidates is not None:
        acc.add((0, float(total_candidates - 1)))
    return acc


def _matches(v: float, acceptable: set[tuple[int, float]]) -> bool:
    return any((p, round(v, p)) in acceptable for p in _PRECISIONS)


def unmatched_tokens(
    narrative_text: str, audit_text: str, total_candidates: int | None = None
) -> list[float]:
    acceptable = acceptable_roundings(extract_numbers(audit_text), total_candidates)
    return [v for v in extract_numbers(narrative_text) if not _matches(v, acceptable)]


def load_narratives() -> dict[str, str]:
    data = json.loads(CACHE_PATH.read_text())
    narratives = data["narratives"]
    # Tolerates both the current {text, provider, model, generated_at} schema and a bare
    # string, so this script keeps working across a schema migration in progress.
    return {k: (v["text"] if isinstance(v, dict) else v) for k, v in narratives.items()}


def main() -> None:
    if not CACHE_PATH.exists():
        print(f"SKIP  {CACHE_PATH} not present")
        sys.exit(0)

    batch = json.loads(DEMO_BATCH_PATH.read_text())
    audit_by_mandate: dict[str, list[dict[str, object]]] = batch["audit_by_mandate"]
    narratives = load_narratives()

    checked = 0
    flagged: list[tuple[str, list[float], str]] = []

    for rows in audit_by_mandate.values():
        for raw in rows:
            decision = _decision_out_from_json(raw)
            key = f"{decision.mandate_id}:{decision.cycle_index}:{decision.attempt_index}"
            narrative = narratives.get(key)
            if narrative is None:
                continue
            checked += 1
            audit_text = render_from_decision_out(decision)
            total_candidates = len(decision.rejected_alternatives) + 1
            unmatched = [
                v
                for v in unmatched_tokens(narrative, audit_text, total_candidates)
                if (key, v) not in WHITELISTED_TOKENS
            ]
            if unmatched:
                flagged.append((key, unmatched, narrative))

    total_unmatched = sum(len(u) for _, u, _ in flagged)
    print(f"checked {checked} narratives ({len(narratives)} cached, {len(flagged)} flagged)")
    print(f"total unmatched numeric tokens: {total_unmatched}")

    if flagged:
        print()
        for key, unmatched, narrative in flagged:
            print(f"  {key}: unmatched {unmatched}")
            print(f"    {narrative}")
        print(
            f"\n{len(flagged)} narrative(s) contain a numeric token not traceable to "
            "their decision's audit record. Read each one: whitelist deliberately "
            "(WHITELISTED_TOKENS, one entry at a time with a reason) if it's legitimate "
            "context, or regenerate the entry if it's a hallucination."
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
