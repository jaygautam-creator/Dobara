from pathlib import Path

import pytest

from sim.params import UnsourcedParameterError, load_params


def test_default_params_load_clean() -> None:
    params = load_params()
    assert params.raw
    assert isinstance(params.assumptions, list)
    assert len(params.assumptions) > 0


def test_unsourced_parameter_fails(tmp_path: Path) -> None:
    bad = tmp_path / "bad_params.yaml"
    bad.write_text("foo:\n  bar:\n    value: 1\n")
    with pytest.raises(UnsourcedParameterError):
        load_params(bad)


def test_sourced_parameter_passes(tmp_path: Path) -> None:
    ok = tmp_path / "ok_params.yaml"
    ok.write_text("foo:\n  bar:\n    value: 1\n    source: 'somewhere'\n")
    params = load_params(ok)
    assert params.get("foo.bar") == 1


def test_assumption_flagged_parameter_passes(tmp_path: Path) -> None:
    ok = tmp_path / "ok_params.yaml"
    ok.write_text("foo:\n  bar:\n    value: 1\n    assumption: true\n")
    params = load_params(ok)
    assert len(params.assumptions) == 1
    assert params.assumptions[0].path == "foo.bar"


def test_structural_scalars_are_not_treated_as_parameters(tmp_path: Path) -> None:
    ok = tmp_path / "ok_params.yaml"
    ok.write_text(
        "contact_hours:\n  start: 8\n  end: 19\ncontact_hours_source: 'cited elsewhere'\n"
    )
    params = load_params(ok)  # must not raise
    assert params.raw["contact_hours"]["start"] == 8
