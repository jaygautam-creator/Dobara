"""Loads sim/params.yaml and enforces that every parameter carries a source or is
flagged as an assumption. See docs/04-DATA-MODEL.md and docs/03-TECH-STACK.md #5.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

DEFAULT_PARAMS_PATH = Path(__file__).parent / "params.yaml"


class UnsourcedParameterError(ValueError):
    """Raised when a parameter leaf has neither `source` nor `assumption: true`."""


@dataclass(frozen=True)
class Assumption:
    path: str
    value: Any
    sensitivity_range: list[float] | None
    note: str | None


@dataclass(frozen=True)
class Params:
    raw: dict[str, Any]
    assumptions: list[Assumption] = field(default_factory=list)

    def get(self, dotted_path: str) -> Any:
        """Resolve a dotted path to a leaf's `value` (e.g. 'revocation.base_hazard_per_cycle')."""
        node: Any = self.raw
        for part in dotted_path.split("."):
            node = node[part]
        if isinstance(node, dict) and "value" in node:
            return node["value"]
        return node


def _is_param_leaf(node: dict[str, Any]) -> bool:
    return "value" in node


def _validate_leaf(path: str, node: dict[str, Any], assumptions: list[Assumption]) -> None:
    has_source = bool(node.get("source"))
    is_assumption = bool(node.get("assumption"))
    if not has_source and not is_assumption:
        raise UnsourcedParameterError(
            f"sim/params.yaml: '{path}' has neither `source:` nor `assumption: true`. "
            "Every simulator parameter must carry one or the other. See docs/04-DATA-MODEL.md."
        )
    if is_assumption:
        assumptions.append(
            Assumption(
                path=path,
                value=node["value"],
                sensitivity_range=node.get("sensitivity_range"),
                note=node.get("note"),
            )
        )


def _walk(node: Any, path: str, assumptions: list[Assumption]) -> None:
    if isinstance(node, dict):
        if _is_param_leaf(node):
            _validate_leaf(path, node, assumptions)
            return
        for key, value in node.items():
            child_path = f"{path}.{key}" if path else key
            _walk(value, child_path, assumptions)
    elif isinstance(node, list):
        for i, item in enumerate(node):
            _walk(item, f"{path}[{i}]", assumptions)
    # scalars (plain structural config, e.g. contact_hours.start) are not parameters


def load_params(path: Path | None = None) -> Params:
    p = path or DEFAULT_PARAMS_PATH
    raw = yaml.safe_load(p.read_text())
    assumptions: list[Assumption] = []
    _walk(raw, "", assumptions)
    return Params(raw=raw, assumptions=assumptions)
