"""Ask one question with either a single SQL attempt or the repair loop.

The loop does not talk to Gemini or PostgreSQL directly. Tests pass a scripted
model and fake tools. ``answer_question`` passes Gemini and the MCP client.
Tool calls are async because the MCP session is async. The model call is sync.
"""

from __future__ import annotations

import time
from typing import Protocol

from agent.prompts import SQL_SYSTEM, SUMMARY_SYSTEM, schema_user, summary_user, with_sql_footer
from agent.runlog import append_run, token_totals
from agent.sql_text import extract_sql
from interfaces.types import AnswerResult, AttemptRecord, LLMCallRecord, QueryPayload, RunConfig


class ChatModel(Protocol):
    """Anything that can complete one prompt and report tokens. Gemini does this."""

    def complete(self, *, system: str, user: str): ...


class ToolClient(Protocol):
    """The three MCP tools, as the agent sees them."""

    async def get_full_schema(self) -> dict: ...

    async def retrieve_schema(self, question: str, k: int) -> dict: ...

    async def run_read_query(self, sql: str) -> QueryPayload: ...


async def run_agent(
    question: str,
    config: RunConfig,
    model: ChatModel,
    tools: ToolClient,
    *,
    log_path=None,
) -> AnswerResult:
    """Answer ``question`` under ``config`` and append a log line."""
    started = time.perf_counter()
    calls: list[LLMCallRecord] = []
    schema_text, schema_error = await _schema_text(question, config, tools)
    if schema_error:
        result = _empty_result(config, schema_error, (time.perf_counter() - started) * 1000)
        if log_path is not None:
            append_run(result, log_path)
        return result

    attempts: list[AttemptRecord] = []
    failures: list[tuple[str, str]] = []
    succeeded: int | None = None
    final_sql: str | None = None
    payload: QueryPayload | None = None
    limit = config.attempt_limit()

    for number in range(1, limit + 1):
        written = model.complete(
            system=SQL_SYSTEM,
            user=schema_user(question, schema_text, failures),
        )
        calls.append(written.as_call("write_sql", number))
        raw = written.text.strip()
        # Keep a non-SELECT reply so the database error can be fed into the repair.
        sql = extract_sql(raw) or raw
        if not sql:
            error = "The model returned an empty response."
            attempts.append({"attempt": number, "sql": "", "error": error, "row_count": None})
            failures.append(("", error))
            continue
        query_result = await tools.run_read_query(sql)
        if not query_result["ok"]:
            error = query_result["error"] or "The query failed."
            attempts.append({"attempt": number, "sql": sql, "error": error, "row_count": None})
            failures.append((sql, error))
            final_sql = sql
            continue
        attempts.append(
            {
                "attempt": number,
                "sql": sql,
                "error": None,
                "row_count": int(query_result["row_count"]),
            }
        )
        succeeded = number
        final_sql = sql
        payload = query_result
        break

    if payload is None:
        last_error = attempts[-1]["error"] if attempts else "No attempt was made."
        answer = (
            f"I could not answer that after {len(attempts)} attempt(s). Last error: {last_error}"
        )
        if final_sql:
            answer += f"\n\nSQL:\n{final_sql}"
        error = last_error
        row_count = None
    else:
        assert final_sql is not None
        summary = model.complete(
            system=SUMMARY_SYSTEM,
            user=summary_user(question, final_sql, payload),
        )
        calls.append(summary.as_call("summarize", None))
        answer = with_sql_footer(summary.text, final_sql, int(payload["row_count"]))
        error = None
        row_count = int(payload["row_count"])

    result: AnswerResult = {
        "answer": answer,
        "sql": final_sql,
        "row_count": row_count,
        "attempts": attempts,
        "attempt_count": len(attempts),
        "succeeded_attempt": succeeded,
        "latency_ms": round((time.perf_counter() - started) * 1000, 3),
        "tokens": token_totals(calls),
        "calls": calls,
        "error": error,
        "schema_mode": config.schema_mode,
        "mode": config.mode,
        "guardrails": config.guardrails,
        "model": config.model,
    }
    if log_path is not None:
        append_run(result, log_path)
    return result


async def _schema_text(question: str, config: RunConfig, tools: ToolClient) -> tuple[str, str | None]:
    if config.schema_mode == "full":
        payload = await tools.get_full_schema()
    else:
        payload = await tools.retrieve_schema(question, config.schema_k)
    error = str(payload.get("error") or "").strip()
    text = str(payload.get("text") or "").strip()
    if error:
        return "", error
    if not text:
        return "", "The schema tool returned no text."
    return text, None


def _empty_result(config: RunConfig, error: str, latency_ms: float) -> AnswerResult:
    return {
        "answer": f"I could not look up the schema. {error}",
        "sql": None,
        "row_count": None,
        "attempts": [],
        "attempt_count": 0,
        "succeeded_attempt": None,
        "latency_ms": round(latency_ms, 3),
        "tokens": {"prompt": 0, "completion": 0, "total": 0},
        "calls": [],
        "error": error,
        "schema_mode": config.schema_mode,
        "mode": config.mode,
        "guardrails": config.guardrails,
        "model": config.model,
    }
