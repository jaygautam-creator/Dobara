"""Provider-agnostic LLM adapter, per docs/03-TECH-STACK.md: "Behind llm/provider.py so
Gemini / Groq / Anthropic / local are one-line swaps." Default is Google Gemini's free
tier. Nothing in `agent/` imports this module or anything that imports it -- narrative
generation never touches the money decision (CLAUDE.md's "Money decisions never pass
through an LLM", enforced elsewhere by `tests/test_import_boundaries.py`).
"""

from __future__ import annotations

import os
import re
import time
from typing import Protocol

import httpx

DEFAULT_GEMINI_MODEL = "gemini-3.5-flash-lite"

# Each named model is its own free-tier quota bucket, sized independently:
# gemini-3.6-flash ("thinking", slow) capped at 20 requests/day; gemini-3.5-flash-lite at
# 500/day (hit mid-batch: 499 decisions narrated before the 500th call 429'd);
# gemini-flash-lite-latest was already exhausted too (it aliases the current best lite
# release, evidently sharing gemini-3.5-flash-lite's bucket); gemini-2.5-flash-lite is
# deprecated (404). gemini-3.1-flash-lite had a fresh bucket and also capped at 500/day
# (993/1296 decisions in, second such ceiling hit in the same batch). gemini-3-flash-preview
# had a further fresh bucket -- a few seconds slower per call (not a lite model) but
# verified against a real audit record before this third switch. A batch this size may
# span several calendar days and/or several model buckets, and that's fine: the cache is
# keyed by decision, not by which model narrated it, and generation is idempotent.
#
# Free-tier 429s come in two shapes that look identical in prose (both say "check your
# plan and billing details") but need opposite handling, distinguished by the response's
# structured quotaId, never by text-matching the message (a first version matched the
# word "billing" and false-positive-aborted a real, retryable RPM=15 limit):
#
#   *PerMinute*-FreeTier -- a short window that clears on its own. Worth retrying, and
#   the response's own "Please retry in Ns" is the right delay to honor.
#
#   *PerDay*-FreeTier -- a hard daily ceiling (discovered twice: gemini-3.6-flash capped
#   at 20/day, gemini-3.5-flash-lite at 500/day). Retrying is pure waste -- every call
#   fails identically until the daily reset -- so this is raised as its own exception
#   instead, and scripts/generate_ask_why.py aborts the whole batch rather than
#   cascading a FAIL through every remaining decision at ~20+ minutes each (30 retries
#   against a quota that won't clear this session).
#
# "prepayment credits are depleted" is a third, unrelated 429 shape (real billing
# exhaustion on the account, not a quota) -- also non-retryable, also raised as
# QuotaExhausted rather than retried.
#
# Groq has its own daily-cap phrasing, caught the hard way: its 429 body said "tokens
# per day (TPD): Limit 200000, Used 200000" and *also* sent a `retry-after: 75` header
# and "please try again in 1m14s" in the message -- both of which look like an ordinary
# short rate limit. They aren't: waiting 75s at an exhausted 200k/200k TPD ceiling does
# not meaningfully replenish it, so the *first* run against Groq spent ~7 minutes stuck
# retrying a call that was never going to succeed before this marker was added.
_RETRY_DELAY_PATTERN = re.compile(r"retry in ([\d.]+)s", re.IGNORECASE)
MAX_RATE_LIMIT_RETRIES = 30
_NON_RETRYABLE_MARKERS = (
    "perday",
    "prepayment credits are depleted",
    "per day (tpd)",
    "tokens per day",
    "requests per day",
)


class QuotaExhausted(RuntimeError):
    """Not transient -- a daily quota ceiling or depleted billing, not a window that
    will clear this session. Don't retry; the caller should stop the whole batch."""


class LLMProvider(Protocol):
    #: Short, stable identifier for who generated a narrative -- "gemini" / "groq" --
    #: stamped onto every cache entry (scripts/generate_ask_why.py) alongside `model`,
    #: since the cache has already been genuinely heterogeneous across both providers
    #: and several models per provider (see docs/DECISIONS.md [2026-08-28]).
    provider_id: str
    model: str

    def generate(self, prompt: str) -> str: ...


class GeminiProvider:
    """Calls Gemini's `generateContent` REST endpoint directly via httpx (already a
    project dependency) rather than adding the `google-generativeai` SDK for a single
    call shape -- keeps the adapter a one-file swap, per the module docstring above."""

    provider_id = "gemini"

    def __init__(self, api_key: str, model: str = DEFAULT_GEMINI_MODEL) -> None:
        self._api_key = api_key
        self.model = model
        # gemini-3.6-flash "thinks" before answering -- several seconds is normal, not a
        # hang, so this needs headroom beyond httpx's 5s default.
        self._client = httpx.Client(timeout=60.0)

    def _post(self, prompt: str) -> httpx.Response:
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent"
        )
        return self._client.post(
            url,
            headers={"x-goog-api-key": self._api_key, "Content-Type": "application/json"},
            json={"contents": [{"parts": [{"text": prompt}]}]},
        )

    def generate(self, prompt: str) -> str:
        resp: httpx.Response | None = None
        for attempt in range(MAX_RATE_LIMIT_RETRIES):
            resp = self._post(prompt)
            if resp.status_code != 429:
                break
            body_lower = resp.text.lower()
            if any(marker in body_lower for marker in _NON_RETRYABLE_MARKERS):
                raise QuotaExhausted(
                    f"Non-retryable quota/billing limit for this session: {resp.text}"
                )
            match = _RETRY_DELAY_PATTERN.search(resp.text)
            # +2s buffer -- the server's own suggested delay is a floor, not a guarantee.
            delay = float(match.group(1)) + 2.0 if match else 20.0 * (attempt + 1)
            time.sleep(delay)
        assert resp is not None
        resp.raise_for_status()
        data = resp.json()
        candidates = data.get("candidates") or []
        if not candidates:
            raise RuntimeError(f"Gemini returned no candidates: {data}")
        parts = candidates[0].get("content", {}).get("parts") or []
        text = "".join(p.get("text", "") for p in parts).strip()
        if not text:
            raise RuntimeError(f"Gemini returned an empty candidate: {data}")
        return text


DEFAULT_GROQ_MODEL = "openai/gpt-oss-120b"


class GroqProvider:
    """Groq's OpenAI-compatible `/chat/completions` endpoint. Added after a single
    evening's `make ask-why` run burned through four separate Gemini free-tier quota
    buckets (20-500 requests/day each -- see the comment above) without finishing a
    ~1,300-decision batch. Groq's free tier is a single, much larger daily allowance per
    model, which is a better fit for a batch job like this than juggling several small
    Gemini buckets across multiple calendar days -- though it turned out to have the
    same per-model-bucket shape: `openai/gpt-oss-20b`'s 200,000 tokens/day budget still
    ran out around decision 1,131/1,296, at which point `openai/gpt-oss-120b` (a
    separate bucket, verified fresh and narration-quality-checked before the switch)
    picked up the rest."""

    provider_id = "groq"

    def __init__(self, api_key: str, model: str = DEFAULT_GROQ_MODEL) -> None:
        self._api_key = api_key
        self.model = model
        self._client = httpx.Client(timeout=60.0)

    def _post(self, prompt: str) -> httpx.Response:
        return self._client.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            json={"model": self.model, "messages": [{"role": "user", "content": prompt}]},
        )

    def generate(self, prompt: str) -> str:
        resp: httpx.Response | None = None
        for attempt in range(MAX_RATE_LIMIT_RETRIES):
            resp = self._post(prompt)
            if resp.status_code != 429:
                break
            body_lower = resp.text.lower()
            if any(marker in body_lower for marker in _NON_RETRYABLE_MARKERS):
                raise QuotaExhausted(
                    f"Non-retryable quota/billing limit for this session: {resp.text}"
                )
            # Groq sends the wait as a Retry-After header, not embedded in the message
            # text the way Gemini does -- prefer it, fall back to the same escalating
            # default Gemini's path uses if it's ever absent.
            retry_after = resp.headers.get("retry-after")
            delay = float(retry_after) + 2.0 if retry_after else 20.0 * (attempt + 1)
            time.sleep(delay)
        assert resp is not None
        resp.raise_for_status()
        data = resp.json()
        choices = data.get("choices") or []
        if not choices:
            raise RuntimeError(f"Groq returned no choices: {data}")
        text = (choices[0].get("message", {}).get("content") or "").strip()
        if not text:
            raise RuntimeError(f"Groq returned an empty choice: {data}")
        return text


def default_provider() -> LLMProvider:
    """`GROQ_API_KEY` wins if set -- Groq's single larger daily quota is the better fit
    for a batch this size (see GroqProvider's docstring). Falls back to `GEMINI_API_KEY`.
    Neither is ever hardcoded or committed; raises loudly if both are unset rather than
    silently writing empty narratives."""
    groq_key = os.environ.get("GROQ_API_KEY")
    if groq_key:
        model = os.environ.get("GROQ_MODEL", DEFAULT_GROQ_MODEL)
        return GroqProvider(api_key=groq_key, model=model)
    gemini_key = os.environ.get("GEMINI_API_KEY")
    if gemini_key:
        model = os.environ.get("GEMINI_MODEL", DEFAULT_GEMINI_MODEL)
        return GeminiProvider(api_key=gemini_key, model=model)
    raise RuntimeError(
        "Neither GROQ_API_KEY nor GEMINI_API_KEY is set. Export one before running "
        "scripts/generate_ask_why.py -- narratives are generated offline and committed, "
        "never called from the deployed (static-export) frontend."
    )
