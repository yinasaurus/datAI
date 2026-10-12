"""Gemini client. The model name comes from the environment, not from this file."""

from __future__ import annotations

import os
import time
from dataclasses import dataclass

from interfaces.types import LLMCallRecord


@dataclass(frozen=True)
class LLMResult:
    """One model call: the text, how long it took, and the token counts."""

    text: str
    latency_ms: float
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int

    def as_call(self, step: str, attempt: int | None) -> LLMCallRecord:
        return {
            "step": step,
            "attempt": attempt,
            "latency_ms": round(self.latency_ms, 3),
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
        }


class GeminiChat:
    """Call Gemini with the temperature and seed from the run config.

    ``GEMINI_API_KEY`` and ``GEMINI_MODEL`` must be set. This class does not
    choose a model name of its own.
    """

    def __init__(self, *, temperature: float, seed: int, model: str = "") -> None:
        self.temperature = temperature
        self.seed = seed
        self.model = model.strip() or os.environ.get("GEMINI_MODEL", "").strip()
        self.api_key = os.environ.get("GEMINI_API_KEY", "").strip()
        if not self.model:
            raise RuntimeError("Set GEMINI_MODEL in role2/.env. The model name is not hardcoded.")
        if not self.api_key:
            raise RuntimeError("Set GEMINI_API_KEY in role2/.env.")

    def complete(self, *, system: str, user: str) -> LLMResult:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=self.api_key)
        started = time.perf_counter()
        try:
            response = client.models.generate_content(
                model=self.model,
                contents=user,
                config=types.GenerateContentConfig(
                    system_instruction=system,
                    temperature=self.temperature,
                    seed=self.seed,
                ),
            )
        except Exception as exc:
            elapsed = (time.perf_counter() - started) * 1000
            return LLMResult(
                text=f"The model call failed: {exc}",
                latency_ms=elapsed,
                prompt_tokens=0,
                completion_tokens=0,
                total_tokens=0,
            )
        elapsed = (time.perf_counter() - started) * 1000
        prompt, completion, total = _usage(response)
        return LLMResult(
            text=_response_text(response),
            latency_ms=elapsed,
            prompt_tokens=prompt,
            completion_tokens=completion,
            total_tokens=total,
        )


def _response_text(response: object) -> str:
    try:
        text = getattr(response, "text", None)
    except Exception as exc:
        return f"The model returned no text: {exc}"
    if isinstance(text, str) and text.strip():
        return text
    return "The model returned no text."


def _usage(response: object) -> tuple[int, int, int]:
    meta = getattr(response, "usage_metadata", None)
    if meta is None:
        return (0, 0, 0)
    prompt = int(getattr(meta, "prompt_token_count", 0) or 0)
    completion = int(getattr(meta, "candidates_token_count", 0) or 0)
    total = int(getattr(meta, "total_token_count", 0) or (prompt + completion))
    return prompt, completion, total
