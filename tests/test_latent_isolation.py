"""`features/` must never import `sim.latent` — that would let the agent observe the
hidden balance process and make the evaluation circular. See docs/04-DATA-MODEL.md and
docs/02-ARCHITECTURE.md (`features/` module contract).
"""

from __future__ import annotations

import ast
from pathlib import Path

FEATURES_DIR = Path(__file__).parent.parent / "features"


def _imported_modules(source: str) -> set[str]:
    tree = ast.parse(source)
    modules = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                modules.add(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    return modules


def test_features_package_has_no_import_path_to_latent() -> None:
    banned = {"sim.latent", "sim.latent_schema"}
    offenders = []
    for py_file in FEATURES_DIR.rglob("*.py"):
        modules = _imported_modules(py_file.read_text())
        hit = modules & banned
        if hit:
            offenders.append((py_file, hit))
    assert not offenders, f"features/ must never import sim.latent: {offenders}"
