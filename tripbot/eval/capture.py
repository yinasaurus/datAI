"""Persist logical calls and physical requests, including partial failures."""
from __future__ import annotations

import json
import os
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def error_info(exc: BaseException) -> dict[str, Any]:
    """Avoid exception messages that can contain credentials or request URLs."""
    code = getattr(exc, "code", None)
    return {"type": type(exc).__name__, "code": code if isinstance(code, int) else None}


def redact(value: Any) -> Any:
    """Remove known process credentials from stored prompts, outputs, and metadata."""
    if isinstance(value, str):
        for key in ("GEMINI_API_KEY", "GOOGLE_API_KEY", "TELEGRAM_BOT_TOKEN", "CANARY_TOKEN"):
            secret = os.environ.get(key, "")
            if secret:
                value = value.replace(secret, "[REDACTED]")
        return value
    if isinstance(value, dict):
        return {key: redact(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [redact(item) for item in value]
    return value


def write_json(path: Path, value: Any) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(redact(value), indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


class CaptureClient:
    """Wrap a client; the existing LLM layer retains exclusive ownership of retries."""

    def __init__(self, inner: Any, path: Path) -> None:
        self.inner = inner
        self.path = path
        self.models = self
        self.logical_calls = 0
        self.requests = 0
        self.active_call: int | None = None
        self.known_in = 0
        self.known_out = 0
        self.unknown_usage_requests = 0
        self.request_seconds = 0.0
        self.logical_seconds = 0.0

    def event(self, **fields: Any) -> None:
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(redact({"utc": utc_now(), **fields})) + "\n")

    @contextmanager
    def logical_call(self, system, prompt, config, json_mode, response_schema):
        self.logical_calls += 1
        self.active_call = self.logical_calls
        started = time.perf_counter()
        self.event(event="logical_started", call=self.active_call, model=config["model"],
                   system=system, prompt=prompt, json_mode=json_mode,
                   response_schema=response_schema)
        try:
            yield
        except BaseException as exc:
            self.event(event="logical_failed", call=self.active_call, error=error_info(exc),
                       seconds=time.perf_counter() - started)
            raise
        else:
            self.event(event="logical_completed", call=self.active_call,
                       seconds=time.perf_counter() - started)
        finally:
            self.logical_seconds += time.perf_counter() - started
            self.active_call = None

    def generate_content(self, *, model, contents, config):
        self.requests += 1
        number = self.requests
        self.event(event="request_started", request=number, call=self.active_call)
        started = time.perf_counter()
        try:
            response = self.inner.models.generate_content(model=model, contents=contents, config=config)
        except BaseException as exc:
            elapsed = time.perf_counter() - started
            self.request_seconds += elapsed
            self.unknown_usage_requests += 1
            self.event(event="request_failed", request=number, call=self.active_call,
                       seconds=elapsed, error=error_info(exc), tokens_in=None, tokens_out=None)
            raise
        elapsed = time.perf_counter() - started
        self.request_seconds += elapsed
        usage = getattr(response, "usage_metadata", None)
        incoming = getattr(usage, "prompt_token_count", None)
        outgoing = getattr(usage, "candidates_token_count", None)
        thoughts = getattr(usage, "thoughts_token_count", None)
        outgoing = outgoing + (thoughts or 0) if outgoing is not None else None
        if incoming is not None:
            self.known_in += incoming
        if outgoing is not None:
            self.known_out += outgoing
        if incoming is None or outgoing is None:
            self.unknown_usage_requests += 1
        self.event(event="request_completed", request=number, call=self.active_call, seconds=elapsed,
                   text=response.text or "", tokens_in=incoming, tokens_out=outgoing)
        return response

    def usage(self) -> dict[str, Any]:
        complete = self.unknown_usage_requests == 0
        return {"logical_calls": self.logical_calls, "physical_requests": self.requests,
                "known_tokens_in": self.known_in, "known_tokens_out": self.known_out,
                "tokens_in": self.known_in if complete else None,
                "tokens_out": self.known_out if complete else None,
                "unknown_usage_requests": self.unknown_usage_requests,
                "request_seconds": self.request_seconds, "logical_call_seconds": self.logical_seconds}
