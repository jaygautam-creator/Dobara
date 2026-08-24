import pytest

from sim.splits import split_for_cycle


@pytest.mark.parametrize(
    "cycle_index,expected",
    [(1, "train"), (4, "train"), (5, "validate"), (6, "test"), (8, "test")],
)
def test_temporal_split(cycle_index: int, expected: str) -> None:
    assert split_for_cycle(cycle_index, is_cold_start=False) == expected


def test_cold_start_overrides_temporal_split() -> None:
    assert split_for_cycle(1, is_cold_start=True) == "cold_start"
    assert split_for_cycle(7, is_cold_start=True) == "cold_start"


def test_out_of_range_cycle_raises() -> None:
    with pytest.raises(ValueError):
        split_for_cycle(9, is_cold_start=False)
