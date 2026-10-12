"""Scripted model and tools so the loop tests do not need Gemini or PostgreSQL."""

from __future__ import annotations

from agent.llm import LLMResult
from interfaces.types import QueryPayload, RunConfig


class ScriptedModel:
    """Return replies in order and record every prompt it was given."""

    def __init__(self, replies: list[str]) -> None:
        self._replies = list(replies)
        self.calls: list[tuple[str, str]] = []

    def complete(self, *, system: str, user: str) -> LLMResult:
        self.calls.append((system, user))
        text = self._replies.pop(0) if self._replies else ""
        return LLMResult(
            text=text,
            latency_ms=1.5,
            prompt_tokens=10,
            completion_tokens=4,
            total_tokens=14,
        )


class FakeTools:
    """Stand-in for the MCP session. Each query pops the next scripted result."""

    def __init__(self, results: list[QueryPayload], schema_error: str = "") -> None:
        self._results = list(results)
        self.schema_error = schema_error
        self.queries: list[str] = []
        self.schema_calls: list[tuple] = []

    async def get_full_schema(self) -> dict:
        self.schema_calls.append(("full",))
        return {"text": "" if self.schema_error else "TABLE orders\n  order_id integer", "error": self.schema_error}

    async def retrieve_schema(self, question: str, k: int) -> dict:
        self.schema_calls.append(("rag", question, k))
        return {
            "text": "" if self.schema_error else "chunk: orders",
            "chunks": [],
            "error": self.schema_error,
        }

    async def run_read_query(self, sql: str) -> QueryPayload:
        self.queries.append(sql)
        if not self._results:
            return _error("No scripted query result was left.")
        return self._results.pop(0)


def config(**overrides: object) -> RunConfig:
    values: dict[str, object] = {
        "schema_mode": "rag",
        "mode": "agent_loop",
        "max_repairs": 3,
        "guardrails": "on",
        "temperature": 0.0,
        "seed": 42,
        "schema_k": 4,
        "model": "scripted",
        "log_path": "logs/runs.jsonl",
    }
    values.update(overrides)
    chosen = RunConfig(
        schema_mode=str(values["schema_mode"]),
        mode=str(values["mode"]),
        max_repairs=int(values["max_repairs"]),
        guardrails=str(values["guardrails"]),
        temperature=float(values["temperature"]),
        seed=int(values["seed"]),
        schema_k=int(values["schema_k"]),
        model=str(values["model"]),
        log_path=str(values["log_path"]),
    )
    chosen.validate()
    return chosen


def query_error(message: str) -> QueryPayload:
    return _error(message)


def query_ok(rows: list[list[object]] | None = None) -> QueryPayload:
    kept = [["delivered", 1]] if rows is None else rows
    return {
        "ok": True,
        "columns": ["status", "n"],
        "rows": kept,
        "row_count": len(kept),
        "error": None,
    }


def _error(message: str) -> QueryPayload:
    return {"ok": False, "columns": [], "rows": [], "row_count": 0, "error": message}
