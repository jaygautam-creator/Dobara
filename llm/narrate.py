"""Turns one decision's structured audit record into a short plain-English narrative --
the `/audit` "ask why" box (docs/08-FRONTEND-SPEC.md). The LLM is given the exact
SAW/THOUGHT/ALT/GATE/DID/WHY text `agent/audit.py::render()` already produced and is
instructed to explain it, not to reconsider, second-guess, or add information beyond it.
This module has no involvement in the decision itself -- it only narrates a decision
already made and logged by `agent/decide.py`, well after the fact.
"""

from __future__ import annotations

import re

from llm.provider import LLMProvider

# Some models (encountered with qwen/qwen3.6-27b on Groq, mid-batch) emit a visible
# <think>...</think> reasoning block before the actual answer even without being asked
# to. Left in, it would corrupt the cache with a chain-of-thought dump instead of the
# short narrative the box is meant to show -- stripped defensively so a future model
# swap that reintroduces this doesn't require noticing it by eye first.
_THINK_BLOCK = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)

_PROMPT_TEMPLATE = """You are explaining one automated payment-retry decision to a \
non-technical reader (a merchant or a regulator), using only the structured audit \
record below. Do not invent facts, numbers, or reasons not present in the record. Do \
not second-guess or evaluate whether the decision was correct -- only explain it. Write \
2-4 plain-English sentences, no bullet points, no headings. Mention the concrete rupee \
figures and the action taken. If the decision was to abstain or stop, say so plainly and \
explain why the model did not act, rather than treating it as a null case.

AUDIT RECORD:
{audit_text}

EXPLANATION:"""


def build_prompt(audit_text: str) -> str:
    return _PROMPT_TEMPLATE.format(audit_text=audit_text)


def narrate(provider: LLMProvider, audit_text: str) -> str:
    raw = provider.generate(build_prompt(audit_text))
    return _THINK_BLOCK.sub("", raw).strip()
