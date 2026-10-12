"""The three tools, without the MCP transport.

The server and the tests both call these functions. SQL errors come back as
``ok: false`` plus a readable ``error``. They are not raised, because the
agent has to read the message and repair the query.
"""

from __future__ import annotations

from collections.abc import Callable

from interfaces.guardrails import check_sql
from interfaces.retriever import load_authored_schema, retrieve
from interfaces.types import GuardrailDecision, QueryPayload, SchemaChunk
from mcp_server.db import DatabaseError, execute_query

_FULL_SCHEMA_SQL = """
SELECT c.table_name, c.column_name, c.data_type
FROM information_schema.columns AS c
JOIN information_schema.tables AS t
  ON t.table_schema = c.table_schema
 AND t.table_name = c.table_name
WHERE c.table_schema = 'public'
  AND t.table_type = 'BASE TABLE'
ORDER BY c.table_name, c.ordinal_position
"""


def execute_sql(
    sql: str,
    *,
    guardrails: str = "on",
    check: Callable[[str], GuardrailDecision] | None = None,
    query: Callable[[str], tuple[list[str], list[list[object]]]] | None = None,
) -> QueryPayload:
    """Run one statement, optionally after the guardrail hook.

    ``guardrails='off'`` skips ``check``. The model cannot pass this flag.
    The evaluation config sets it on the server process.
    """
    if guardrails not in ("on", "off"):
        return _failed("guardrails must be 'on' or 'off'.")
    if not isinstance(sql, str) or not sql.strip():
        return _failed("SQL is empty.")

    if guardrails == "on":
        decision = (check or check_sql)(sql)
        if not decision.allowed:
            reason = decision.reason.strip() or "The guardrail harness blocked this query."
            return _failed(reason)

    try:
        columns, rows = (query or execute_query)(sql)
    except DatabaseError as exc:
        return _failed(str(exc))
    return {
        "ok": True,
        "columns": columns,
        "rows": rows,
        "row_count": len(rows),
        "error": None,
    }


def get_full_schema() -> dict[str, str]:
    """Schema for the no-RAG baseline.

    Prefer Role 1's authored file. Otherwise list public tables from PostgreSQL.
    """
    authored = load_authored_schema()
    if authored:
        return {"text": authored, "error": ""}
    try:
        _columns, rows = execute_query(_FULL_SCHEMA_SQL)
    except DatabaseError as exc:
        return {"text": "", "error": str(exc)}
    return {"text": _format_columns(rows), "error": ""}


def retrieve_schema(question: str, k: int = 4) -> dict[str, object]:
    """Schema for the RAG condition. Calls Role 1's ``retrieve``."""
    chunks = retrieve(question, k)
    return {
        "text": format_chunks(chunks),
        "chunks": [{"id": chunk.id, "source": chunk.source, "text": chunk.text} for chunk in chunks],
        "error": "",
    }


def format_chunks(chunks: list[SchemaChunk]) -> str:
    """Wrap chunks so the model can see where untrusted schema text starts."""
    if not chunks:
        return "No schema chunks were retrieved."
    parts: list[str] = []
    for index, chunk in enumerate(chunks, start=1):
        parts.append(
            f"[schema chunk {index} | id={chunk.id} | source={chunk.source}]\n{chunk.text.strip()}"
        )
    return "\n\n".join(parts)


def _format_columns(rows: list[list[object]]) -> str:
    if not rows:
        return "The public schema has no tables."
    grouped: dict[str, list[str]] = {}
    for row in rows:
        table = str(row[0])
        column = str(row[1])
        data_type = str(row[2])
        grouped.setdefault(table, []).append(f"  {column} {data_type}")
    blocks = [f"TABLE {name}\n" + "\n".join(columns) for name, columns in grouped.items()]
    return "\n\n".join(blocks)


def _failed(message: str) -> QueryPayload:
    return {
        "ok": False,
        "columns": [],
        "rows": [],
        "row_count": 0,
        "error": message,
    }
