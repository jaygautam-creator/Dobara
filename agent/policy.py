"""Loads `config/policy.yaml` — every knob `agent/decide.py` reads, with the same
source-or-assumption discipline as `sim/params.yaml`. Reuses `sim.params.load_params`
directly rather than duplicating its validator: the two files share the exact same
`value` / `source` / `assumption` leaf shape (docs/04-DATA-MODEL.md's
`sim/params.yaml` shape section), so a second copy of the same forty lines would be
pure duplication, not a distinct concern.
"""

from __future__ import annotations

from pathlib import Path

from sim.params import Params, load_params

DEFAULT_POLICY_PATH = Path(__file__).parent.parent / "config" / "policy.yaml"

# `PolicyConfig` is `Params` under a name that reads correctly at agent/decide.py call
# sites (`config.get("max_attempts_per_cycle")`) — see docs/06-AGENT-SPEC.md's
# `decide(ctx, models, config)` signature.
PolicyConfig = Params


def load_policy(path: Path | None = None) -> PolicyConfig:
    return load_params(path or DEFAULT_POLICY_PATH)
