"""Gemini client used by every planning setup.

``call_llm`` reads the model, temperature, and seed from config. It retries
rate limits and transient HTTP failures with exponential backoff, can reuse a
disk cache under ``.cache/``, and appends one JSON line per call.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import httpx
from google import genai
from google.genai import errors, types

RETRY_STATUS_CODES = {408, 429, 500, 502, 503, 504}
MAX_ATTEMPTS = 4
BACKOFF_SECONDS = 1.0

@dataclass(frozen=True)
class LLMResult:
    """One model call, or a cache hit that stands in for one."""

    text: str
    tokens_in: int
    tokens_out: int
    seconds: float
    cached: bool


def call_llm(
    system: str,
    prompt: str,
    config: dict[str, Any],
    json_mode: bool = True,
    *,
    client: Any = None,
    sleeper: Callable[[float], None] = time.sleep,
    response_schema: dict[str, Any] | None = None,
) -> LLMResult:
    """Call Gemini, or return the cached text when ``config['cache']`` is true.

    The cache key is a hash of the model, system prompt, user prompt, and
    temperature. The seed is sent to the API and is not part of that key.
    A provided ``client`` is used as-is, which is how tests avoid the network.
    """
    started = time.perf_counter()
    model = str(config["model"])
    temperature = config["temperature"]
    seed = config["seed"]
    cache_path = _cache_path(model, system, prompt, temperature)
    if _cache_enabled(config):
        cached = _read_cache(cache_path)
        if cached is not None:
            result = LLMResult(
                text=str(cached["text"]),
                tokens_in=int(cached.get("tokens_in", 0)),
                tokens_out=int(cached.get("tokens_out", 0)),
                seconds=time.perf_counter() - started,
                cached=True,
            )
            _append_log(config, result, model, temperature, seed, json_mode, attempts=0, error=None)
            return result

    active = client if client is not None else _build_client()
    request = _request_config(system, temperature, seed, json_mode, response_schema)
    last_error: Exception | None = None
    response: Any = None
    attempts = 0
    for attempt in range(1, MAX_ATTEMPTS + 1):
        attempts = attempt
        try:
            response = active.models.generate_content(
                model=model,
                contents=prompt,
                config=request,
            )
            last_error = None
            break
        except Exception as exc:
            last_error = exc
            if attempt == MAX_ATTEMPTS or not _retryable(exc):
                _append_log(
                    config,
                    None,
                    model,
                    temperature,
                    seed,
                    json_mode,
                    attempts=attempt,
                    error=str(exc),
                    seconds=time.perf_counter() - started,
                )
                raise
            sleeper(BACKOFF_SECONDS * (2 ** (attempt - 1)))

    if response is None:
        raise RuntimeError("model call produced no response") from last_error

    tokens_in, tokens_out = _token_counts(getattr(response, "usage_metadata", None))
    text = response.text or ""
    result = LLMResult(
        text=text,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        seconds=time.perf_counter() - started,
        cached=False,
    )
    if _cache_enabled(config):
        _write_cache(cache_path, result)
    _append_log(config, result, model, temperature, seed, json_mode, attempts=attempts, error=None)
    return result


def _build_client() -> genai.Client:
    """Build a Gemini client. The SDK reads ``GEMINI_API_KEY`` from the environment."""
    from dotenv import load_dotenv

    load_dotenv()
    return genai.Client(
        http_options=types.HttpOptions(
            retry_options=types.HttpRetryOptions(attempts=1),
        )
    )


def _request_config(
    system: str,
    temperature: Any,
    seed: Any,
    json_mode: bool,
    response_schema: dict[str, Any] | None,
) -> types.GenerateContentConfig:
    kwargs: dict[str, Any] = {
        "system_instruction": system,
        "temperature": temperature,
        "seed": seed,
    }
    if json_mode:
        kwargs["response_mime_type"] = "application/json"
        if response_schema is not None:
            kwargs["response_json_schema"] = response_schema
    return types.GenerateContentConfig(**kwargs)


def _retryable(exc: Exception) -> bool:
    if isinstance(exc, errors.APIError):
        return exc.code in RETRY_STATUS_CODES
    return isinstance(exc, (httpx.TransportError, TimeoutError, ConnectionError))


def _token_counts(usage: Any) -> tuple[int, int]:
    if usage is None:
        return 0, 0
    incoming = int(getattr(usage, "prompt_token_count", 0) or 0)
    outgoing = int(getattr(usage, "candidates_token_count", 0) or 0)
    outgoing += int(getattr(usage, "thoughts_token_count", 0) or 0)
    return incoming, outgoing


def _cache_enabled(config: dict[str, Any]) -> bool:
    return bool(config.get("cache", False))


def _cache_path(model: str, system: str, prompt: str, temperature: Any) -> Path:
    payload = json.dumps(
        {
            "model": model,
            "system": system,
            "prompt": prompt,
            "temperature": temperature,
        },
        sort_keys=True,
        ensure_ascii=False,
    )
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return Path(".cache") / f"{digest}.json"


def _read_cache(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(loaded, dict) or "text" not in loaded:
        return None
    return loaded


def _write_cache(path: Path, result: LLMResult) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "text": result.text,
        "tokens_in": result.tokens_in,
        "tokens_out": result.tokens_out,
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def _append_log(
    config: dict[str, Any],
    result: LLMResult | None,
    model: str,
    temperature: Any,
    seed: Any,
    json_mode: bool,
    *,
    attempts: int,
    error: str | None,
    seconds: float | None = None,
) -> None:
    path = Path(config["paths"]["llm_log"])
    path.parent.mkdir(parents=True, exist_ok=True)
    row = {
        "model": model,
        "temperature": temperature,
        "seed": seed,
        "json_mode": json_mode,
        "cached": result.cached if result is not None else False,
        "tokens_in": result.tokens_in if result is not None else 0,
        "tokens_out": result.tokens_out if result is not None else 0,
        "seconds": result.seconds if result is not None else seconds,
        "attempts": attempts,
        "error": error,
    }
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row) + "\n")
