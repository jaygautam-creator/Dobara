"""Split assignment over a simulated World, matching docs/04-DATA-MODEL.md:

- Temporal, by cycle: train 1-4, validate 5, test 6-8. Never a random row split — cycles
  of the same mandate are correlated and a random split leaks.
- Cold-start: `Mandate.is_cold_start` mandates are held out of training entirely.
- Regime shift: `Mandate.regime_shift_bank` mandates carry an injected shift from
  `regime_shift.applies_from_cycle_index` onward (test window only) and must be reported
  as a separate slice, never folded into the headline test metric.
"""

from __future__ import annotations

TRAIN_CYCLES = (1, 4)
VALIDATE_CYCLE = 5
TEST_CYCLES = (6, 8)


def split_for_cycle(cycle_index: int, is_cold_start: bool) -> str:
    if is_cold_start:
        return "cold_start"
    if TRAIN_CYCLES[0] <= cycle_index <= TRAIN_CYCLES[1]:
        return "train"
    if cycle_index == VALIDATE_CYCLE:
        return "validate"
    if TEST_CYCLES[0] <= cycle_index <= TEST_CYCLES[1]:
        return "test"
    raise ValueError(f"cycle_index {cycle_index} outside the configured 1-8 cycle range")
