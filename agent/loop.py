"""Ask a question: retrieve schema, generate SQL, run it, retry, then summarize.

Each call appends one JSON record for later evaluation. The record includes the
retrieved schema, every generated statement, the attempt count, and the final answer.
"""

from __future__ import annotations

import asyncio
import json
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.types import CallToolResult, TextContent

from agent.llm import ChatModel, OpenAIChat, extract_sql
from agent.prompts import SQL_SYSTEM, SUMMARY_SYSTEM, schema_block, sql_user, summary_user
from db import AS_OF_DATE
from rag import retrieve

ROOT = Path(__file__).resolve().parents[1]
SERVER = ROOT / "mcp_server" / "server.py"
DEFAULT_LOG_PATH = Path(__file__).resolve().parent / "logs" / "runs.jsonl"

MAX_ATTEMPTS = 3
SCHEMA_K = 4
SUMMARY_ROW_CAP = 20


@dataclass
class Attempt:
    attempt: int
    sql: str
    error: str | None
    row_count: int | None
    truncated: bool | None

    def to_dict(self) -> dict:
        return {
            "attempt": self.attempt,
            "sql": self.sql,
            "error": self.error,
            "row_count": self.row_count,
            "truncated": self.truncated,
        }


@dataclass
class AgentRun:
    question: str
    retrieved_schema: list[dict]
    attempts: list[Attempt]
    attempt_count: int
    sql: str | None
    final_answer: str
    success: bool
    logged_at: str

    def to_dict(self) -> dict:
        return {
            "question": self.question,
            "retrieved_schema": self.retrieved_schema,
            "attempts": [item.to_dict() for item in self.attempts],
            "attempt_count": self.attempt_count,
            "sql": self.sql,
            "final_answer": self.final_answer,
            "success": self.success,
            "logged_at": self.logged_at,
            "as_of_date": AS_OF_DATE,
        }


def ask(
    question: str,
    *,
    model: ChatModel | None = None,
    k: int = SCHEMA_K,
    log_path: Path | None = None,
) -> AgentRun:
    """Answer one natural-language question and append a log record."""
    if not question or not question.strip():
        raise ValueError("Question is empty.")
    chat = model if model is not None else OpenAIChat()
    run = asyncio.run(_ask(question.strip(), chat, k))
    append_log(run, log_path or DEFAULT_LOG_PATH)
    return run


def append_log(run: AgentRun, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(run.to_dict(), ensure_ascii=False) + "\n")


async def _ask(question: str, model: ChatModel, k: int) -> AgentRun:
    hits = retrieve(question, k=k)
    schema = [
        {
            "id": hit.id,
            "title": hit.title,
            "kind": hit.kind,
            "score": hit.score,
            "text": hit.text,
        }
        for hit in hits
    ]
    schema_text = schema_block(schema)
    attempts: list[Attempt] = []
    failures: list[tuple[str, str]] = []
    answer = ""
    success = False
    final_sql: str | None = None

    params = StdioServerParameters(
        command=sys.executable,
        args=["-u", str(SERVER)],
        cwd=str(ROOT),
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            for number in range(1, MAX_ATTEMPTS + 1):
                raw = model.complete(
                    system=SQL_SYSTEM,
                    user=sql_user(question, schema_text, failures),
                )
                # Prefer a SELECT pulled out of the reply. Anything else is still
                # sent to the server so its rejection becomes the next attempt's error.
                sql = extract_sql(raw) or raw.strip()
                if not sql:
                    error = "The model returned an empty response."
                    attempts.append(Attempt(number, "", error, None, None))
                    failures.append(("", error))
                    continue
                result, error = await _run_read_query(session, sql)
                if error is not None:
                    attempts.append(Attempt(number, sql, error, None, None))
                    failures.append((sql, error))
                    continue
                assert result is not None
                attempts.append(
                    Attempt(
                        number,
                        sql,
                        None,
                        int(result["row_count"]),
                        bool(result["truncated"]),
                    )
                )
                final_sql = sql
                success = True
                answer = model.complete(
                    system=SUMMARY_SYSTEM,
                    user=summary_user(question, sql, result, SUMMARY_ROW_CAP),
                ).strip()
                if not answer:
                    answer = "The query ran, but the summary was empty."
                break

    if not success:
        last_error = attempts[-1].error if attempts else "No attempt was made."
        final_sql = attempts[-1].sql if attempts else None
        answer = (
            f"I could not answer that after {MAX_ATTEMPTS} attempts. Last error: {last_error}"
        )

    return AgentRun(
        question=question,
        retrieved_schema=schema,
        attempts=attempts,
        attempt_count=len(attempts),
        sql=final_sql,
        final_answer=answer,
        success=success,
        logged_at=datetime.now(timezone.utc).isoformat(),
    )


async def _run_read_query(
    session: ClientSession, sql: str
) -> tuple[dict | None, str | None]:
    result = await session.call_tool("run_read_query", {"sql": sql})
    if result.isError:
        return None, _tool_text(result) or "The query was rejected."
    data = _tool_data(result)
    if "rows" not in data or "columns" not in data:
        return None, "The query tool returned an unexpected payload."
    return data, None


def _tool_text(result: CallToolResult) -> str:
    parts: list[str] = []
    for block in result.content:
        if isinstance(block, TextContent):
            parts.append(block.text)
    return "\n".join(parts).strip()


def _tool_data(result: CallToolResult) -> dict:
    if result.structuredContent is not None:
        data = result.structuredContent
    else:
        data = json.loads(_tool_text(result))
    if isinstance(data, dict) and "rows" not in data and isinstance(data.get("result"), dict):
        return data["result"]
    return data
