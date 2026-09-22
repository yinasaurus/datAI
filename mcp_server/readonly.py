"""Read-only SQLite access used by the MCP tools.

Queries go through ``guardrails.execute_read_query``. That layer rejects
writes, applies the table and column allow-lists, blocks sensitive columns,
caps rows, and cancels slow queries. Catalog reads for list_tables and
describe_table use a separate connection with no authorizer, because they
have to inspect sqlite_master. Sensitive columns are removed from describe
results.
"""

from __future__ import annotations

import re
import sqlite3

from pydantic import BaseModel, Field

from db import DB_PATH
from guardrails import (
    POLICY,
    GuardrailViolation,
    ensure_visible,
    execute_read_query,
    filter_visible,
    visible_column_names,
)

MAX_ROWS = POLICY.max_rows
TIMEOUT_SECONDS = POLICY.timeout_seconds

_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class QueryError(Exception):
    """The agent's SQL was rejected or failed."""


class TableSummary(BaseModel):
    name: str
    type: str = Field(description="table or view")


class TableList(BaseModel):
    tables: list[TableSummary]


class ColumnInfo(BaseModel):
    name: str
    type: str
    not_null: bool
    primary_key: bool
    default: str | None = None


class ForeignKeyInfo(BaseModel):
    column: str
    references_table: str
    references_column: str


class TableDescription(BaseModel):
    name: str
    type: str
    columns: list[ColumnInfo]
    foreign_keys: list[ForeignKeyInfo]


class QueryResult(BaseModel):
    columns: list[str]
    rows: list[list[str | int | float | bool | None]]
    row_count: int
    truncated: bool
    row_limit: int


def list_tables() -> TableList:
    """Return application tables and views, after the guardrail visibility hook."""
    with _connect() as conn:
        found = conn.execute(
            """
            SELECT name, type
            FROM sqlite_master
            WHERE type IN ('table', 'view')
              AND name NOT LIKE 'sqlite_%'
            ORDER BY name
            """
        ).fetchall()
    names = filter_visible([row["name"] for row in found])
    visible = set(names)
    tables = [
        TableSummary(name=row["name"], type=row["type"])
        for row in found
        if row["name"] in visible
    ]
    return TableList(tables=tables)


def describe_table(table_name: str) -> TableDescription:
    """Return columns and foreign keys for one table or view."""
    ensure_visible(table_name)
    with _connect() as conn:
        row = _lookup_object(conn, table_name)
        if row is None:
            raise QueryError(
                f"Unknown table or view {table_name!r}. Call list_tables for the available names."
            )
        name = row["name"]
        quoted = _quote_ident(name)
        infos = conn.execute(f"PRAGMA table_info({quoted})").fetchall()
        shown = set(visible_column_names(name, [info["name"] for info in infos]))
        columns = [
            ColumnInfo(
                name=info["name"],
                type=info["type"] or "",
                not_null=bool(info["notnull"]),
                primary_key=bool(info["pk"]),
                default=None if info["dflt_value"] is None else str(info["dflt_value"]),
            )
            for info in infos
            if info["name"] in shown
        ]
        foreign_keys = [
            ForeignKeyInfo(
                column=fk["from"],
                references_table=fk["table"],
                references_column=fk["to"],
            )
            for fk in conn.execute(f"PRAGMA foreign_key_list({quoted})").fetchall()
        ]
    return TableDescription(
        name=name,
        type=row["type"],
        columns=columns,
        foreign_keys=foreign_keys,
    )


def run_read_query(sql: str) -> QueryResult:
    """Execute one SELECT and return at most MAX_ROWS rows."""
    try:
        guarded = execute_read_query(sql)
    except GuardrailViolation as exc:
        raise QueryError(str(exc)) from exc
    return QueryResult(
        columns=guarded.columns,
        rows=guarded.rows,
        row_count=guarded.row_count,
        truncated=guarded.truncated,
        row_limit=guarded.row_limit,
    )


def _connect() -> sqlite3.Connection:
    if not DB_PATH.is_file():
        raise QueryError(f"Database not found at {DB_PATH}. Run python db/seed_data.py first.")
    uri = f"{DB_PATH.resolve().as_uri()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA query_only = ON")
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _lookup_object(conn: sqlite3.Connection, table_name: str) -> sqlite3.Row | None:
    if not isinstance(table_name, str) or not _IDENT.fullmatch(table_name):
        raise QueryError(
            "Table name must be letters, digits, and underscores, and must start with a letter or underscore."
        )
    return conn.execute(
        """
        SELECT name, type
        FROM sqlite_master
        WHERE name = ? COLLATE NOCASE
          AND type IN ('table', 'view')
          AND name NOT LIKE 'sqlite_%'
        """,
        (table_name,),
    ).fetchone()


def _quote_ident(name: str) -> str:
    if not _IDENT.fullmatch(name):
        raise QueryError(f"Unsafe identifier {name!r}.")
    return '"' + name.replace('"', '""') + '"'


