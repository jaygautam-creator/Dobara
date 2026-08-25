"""Deterministic per-event RNG for the batch evaluation harness (`eval/`). Every arm must
face "the same world" for a given seed (docs/07-EVAL-SPEC.md: "All arms run over the
identical held-out batch, identical seeds, identical simulator state") — but arms attempt
on different days and different counts, so a single sequential `np.random.Generator`
would let two arms' draws for the "same" event diverge purely because of *when* an
earlier, unrelated event happened to consume randomness, not because the arms actually
differ.

`event_rng` fixes this: each stochastic draw (an attempt outcome, a revocation roll, a
date-change-offer response) is keyed by stable event identity (seed, mandate id, cycle
index, attempt index, draw name) via a SHA-256 digest — not Python's built-in `hash()`,
which is process-randomized for strings unless `PYTHONHASHSEED` is pinned; see
`models/recovery.py::_model_version` for the same digest-based-determinism technique used
elsewhere in this codebase. "Mandate X's cycle 3, attempt 1, outcome draw" therefore
produces the same random numbers no matter which arm triggers it or on what calendar day.
Arms diverge only through which attempts they choose to make — the fair comparison the
eval spec requires.

This also buys "common random numbers" for the sensitivity sweep: sweeping
`hazard_per_failure_notification` reuses the identical attempt-outcome draws (that
parameter never enters `attempt_outcome`) and only changes the threshold each revocation
roll is compared against, so the sweep curve reflects the parameter's effect rather than
being swamped by re-randomized seed noise.
"""

from __future__ import annotations

import hashlib

import numpy as np


def event_rng(*key_parts: object) -> np.random.Generator:
    """A fresh, independent `Generator` fully determined by `key_parts`. Call with a
    stable identity tuple, e.g. `event_rng(seed, mandate_id, cycle_index, attempt_index,
    "outcome")` — the draw name suffix keeps two different rolls for the same
    attempt (e.g. the outcome draw and a later revocation roll) independent of one
    another rather than accidentally sharing a stream.
    """
    payload = "|".join(str(p) for p in key_parts)
    digest = hashlib.sha256(payload.encode()).digest()
    seed = int.from_bytes(digest[:8], "big")
    return np.random.default_rng(seed)
