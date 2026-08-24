"""`models/` and `agent/decide.py` must never import the LLM layer — money decisions are
tabular, calibrated, and inspectable; LLMs are for narrative/language only
(docs/05-ML-SPEC.md, docs/03-TECH-STACK.md #LLM boundary). AST-based, same technique as
`tests/test_latent_isolation.py`.
"""

from __future__ import annotations

import ast
from pathlib import Path

MODELS_DIR = Path(__file__).parent.parent / "models"
AGENT_DECIDE = Path(__file__).parent.parent / "agent" / "decide.py"

BANNED_SUBSTRINGS = ("llm", "openai", "anthropic", "google.generativeai", "genai")


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


def _banned_hits(modules: set[str]) -> set[str]:
    return {m for m in modules if any(bad in m.lower() for bad in BANNED_SUBSTRINGS)}


def test_models_package_has_no_llm_import() -> None:
    offenders = []
    for py_file in MODELS_DIR.rglob("*.py"):
        hits = _banned_hits(_imported_modules(py_file.read_text()))
        if hits:
            offenders.append((py_file, hits))
    assert not offenders, f"models/ must never import the LLM layer: {offenders}"


def test_agent_decide_has_no_llm_import() -> None:
    if not AGENT_DECIDE.exists():
        return  # agent/decide.py doesn't exist yet (Phase 3); nothing to check
    hits = _banned_hits(_imported_modules(AGENT_DECIDE.read_text()))
    assert not hits, f"agent/decide.py must never import the LLM layer: {hits}"
