"""Read-only SQL policy: statement shape, table and column allow-lists, limits.

The allow-list is the columns declared in schema.sql, minus the sensitive
columns in ``db.SENSITIVE_COLUMNS``, plus the columns of the ``current_term``
view. SQLite's authorizer is the backstop for ``SELECT *``, aliases, and
catalog tables. The text scan rejects destructive statements before they run.
"""

from __future__ import annotations

import re
import sqlite3
import time
from dataclasses import dataclass

from db import DB_PATH, SCHEMA_PATH, SENSITIVE_COLUMNS
from guardrails.injection import sanitize_untrusted

_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_SKIP_CLAUSE = re.compile(r"^(primary|foreign|unique|check|constraint)\b", re.IGNORECASE)
# REPLACE( is the SQL function, so only "REPLACE INTO" is a write.
_FORBIDDEN = re.compile(
    r"\b("
    r"INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|ATTACH|DETACH|REINDEX|VACUUM|"
    r"PRAGMA|ANALYZE|GRANT|REVOKE|TRUNCATE|BEGIN|COMMIT|ROLLBACK|SAVEPOINT|"
    r"LOAD_EXTENSION|REPLACE\s+INTO"
    r")\b",
    re.IGNORECASE,
)
_CATALOG_TABLES = frozenset({"sqlite_master", "sqlite_temp_master", "sqlite_schema"})
_CATALOG = re.compile(r"\b(sqlite_master|sqlite_temp_master|sqlite_schema)\b", re.IGNORECASE)
_DENIED_FUNCTIONS = frozenset({"load_extension", "readfile", "writefile", "edit", "fts3_tokenizer"})
_WRITE_ACTIONS = frozenset(
    {
        sqlite3.SQLITE_INSERT,
        sqlite3.SQLITE_UPDATE,
        sqlite3.SQLITE_DELETE,
        sqlite3.SQLITE_DROP_TABLE,
        sqlite3.SQLITE_DROP_VIEW,
        sqlite3.SQLITE_DROP_INDEX,
        sqlite3.SQLITE_DROP_TRIGGER,
        sqlite3.SQLITE_DROP_VTABLE,
        sqlite3.SQLITE_ALTER_TABLE,
        sqlite3.SQLITE_CREATE_INDEX,
        sqlite3.SQLITE_CREATE_TABLE,
        sqlite3.SQLITE_CREATE_TEMP_INDEX,
        sqlite3.SQLITE_CREATE_TEMP_TABLE,
        sqlite3.SQLITE_CREATE_TEMP_TRIGGER,
        sqlite3.SQLITE_CREATE_TEMP_VIEW,
        sqlite3.SQLITE_CREATE_TRIGGER,
        sqlite3.SQLITE_CREATE_VIEW,
        sqlite3.SQLITE_CREATE_VTABLE,
        sqlite3.SQLITE_ATTACH,
        sqlite3.SQLITE_DETACH,
        sqlite3.SQLITE_PRAGMA,
        sqlite3.SQLITE_REINDEX,
        sqlite3.SQLITE_ANALYZE,
    }
)

_VIEW_SQL = re.compile(
    r"CREATE\s+VIEW\s+(\w+)\s+AS\s+SELECT\s+(.*?)\s+FROM\s",
    re.IGNORECASE | re.DOTALL,
)


class GuardrailViolation(Exception):
    """A query or a table reference was rejected by policy."""


@dataclass(frozen=True)
class GuardrailPolicy:
    allowed_tables: frozenset[str]
    allowed_columns: frozenset[str]
    blocked_columns: frozenset[str]
    database_objects: frozenset[str] = frozenset()
    max_rows: int = 500
    timeout_seconds: float = 5.0
    enforce: bool = True


@dataclass(frozen=True)
class GuardedResult:
    columns: list[str]
    rows: list[list[str | int | float | bool | None]]
    row_count: int
    truncated: bool
    row_limit: int


def load_policy() -> GuardrailPolicy:
    """Build the allow-list from schema.sql and the sensitive-column list."""
    schema = SCHEMA_PATH.read_text(encoding="utf-8")
    tables = _table_columns(schema)
    if len(tables) < 8:
        raise RuntimeError(f"Expected at least 8 tables in {SCHEMA_PATH.name}, found {len(tables)}.")
    blocked = frozenset(name.lower() for name in SENSITIVE_COLUMNS)
    allowed_columns: set[str] = set()
    for table, columns in tables.items():
        for column in columns:
            qualified = f"{table}.{column}"
            if qualified not in blocked:
                allowed_columns.add(qualified)
    allowed_tables = set(tables)
    for match in _VIEW_SQL.finditer(schema):
        view = match.group(1).lower()
        allowed_tables.add(view)
        for column in _split_commas(match.group(2)):
            name = column.strip().split()[0].strip('"')
            if _IDENT.fullmatch(name):
                allowed_columns.add(f"{view}.{name.lower()}")
    missing = [name for name in blocked if name not in {f"{t}.{c}" for t, cols in tables.items() for c in cols}]
    if missing:
        raise RuntimeError(f"Sensitive columns not found in schema.sql: {', '.join(missing)}")
    return GuardrailPolicy(
        allowed_tables=frozenset(allowed_tables),
        allowed_columns=frozenset(allowed_columns),
        blocked_columns=blocked,
        database_objects=_database_objects(),
    )


def check_query(sql: str, policy: GuardrailPolicy | None = None) -> str:
    """Reject anything that is not one allow-listed SELECT. Return the cleaned SQL."""
    if policy is None:
        policy = POLICY
    statement, probe = extract_select(sql)
    if not policy.enforce:
        return statement
    _reject_blocked_identifiers(probe, policy)
    _compile(statement, policy)
    return statement


def execute_read_query(sql: str, policy: GuardrailPolicy | None = None) -> GuardedResult:
    """Check a query, then run it with the authorizer, row cap, and timeout."""
    if policy is None:
        policy = POLICY
    statement = check_query(sql, policy)
    return fetch_rows(statement, policy)


def fetch_rows(statement: str, policy: GuardrailPolicy | None = None) -> GuardedResult:
    """Run a statement that already passed ``check_query``."""
    if policy is None:
        policy = POLICY
    limited = f"SELECT * FROM ({statement}) AS _mcp_limited LIMIT {policy.max_rows + 1}"
    conn = _connect()
    try:
        _install(conn, policy)
        deadline = time.monotonic() + policy.timeout_seconds
        conn.set_progress_handler(_interrupt_after(deadline), 1000)
        try:
            cursor = conn.execute(limited)
            raw_rows = cursor.fetchall()
        except sqlite3.Error as exc:
            raise GuardrailViolation(_explain_sqlite_error(exc, policy)) from exc
        columns = [sanitize_untrusted(item[0]) for item in cursor.description or ()]
    finally:
        conn.set_progress_handler(None, 0)
        conn.close()

    truncated = len(raw_rows) > policy.max_rows
    kept = raw_rows[: policy.max_rows]
    rows = [[_json_cell(value) for value in row] for row in kept]
    return GuardedResult(
        columns=columns,
        rows=rows,
        row_count=len(rows),
        truncated=truncated,
        row_limit=policy.max_rows,
    )


def filter_visible(names: list[str], policy: GuardrailPolicy | None = None) -> list[str]:
    """Keep catalog names that are on the table allow-list."""
    if policy is None:
        policy = POLICY
    if not policy.enforce:
        return list(names)
    allowed = policy.allowed_tables
    return [name for name in names if name.lower() in allowed]


def ensure_visible(name: str, policy: GuardrailPolicy | None = None) -> None:
    """Raise if a table or view is not on the allow-list."""
    if policy is None:
        policy = POLICY
    if not policy.enforce:
        return
    if not isinstance(name, str) or name.lower() not in policy.allowed_tables:
        raise GuardrailViolation(f"Table {name!r} is not available.")


def visible_column_names(table: str, names: list[str], policy: GuardrailPolicy | None = None) -> list[str]:
    """Drop sensitive columns from a describe_table result."""
    if policy is None:
        policy = POLICY
    if not policy.enforce:
        return list(names)
    hidden = _blocked_names_for(table, policy)
    return [name for name in names if name.lower() not in hidden]


def extract_select(sql: str) -> tuple[str, str]:
    """Return ``(executable_sql, keyword_probe)`` or raise GuardrailViolation.

    Comments are removed from both copies. String and quoted-identifier contents
    stay in the executable copy and are blanked in the probe, so a literal such
    as 'DROP' is not treated as a statement.
    """
    if not isinstance(sql, str) or not sql.strip():
        raise GuardrailViolation("SQL is empty.")
    if "\x00" in sql:
        raise GuardrailViolation("SQL contains a null byte.")
    cleaned, masked = _scan(sql)
    statement = _strip_trailing_semicolons(cleaned)
    probe = _strip_trailing_semicolons(masked)
    if not statement or not probe:
        raise GuardrailViolation("SQL is empty.")
    if ";" in probe:
        raise GuardrailViolation("Only a single SELECT statement is allowed.")
    first = probe.split(None, 1)[0].upper()
    if first not in {"SELECT", "WITH"}:
        raise GuardrailViolation("Only SELECT statements are allowed.")
    if _FORBIDDEN.search(probe):
        raise GuardrailViolation("Only SELECT statements are allowed.")
    if _CATALOG.search(probe):
        raise GuardrailViolation("Query blocked by guardrails: catalog tables cannot be read.")
    return statement, probe


def _reject_blocked_identifiers(probe: str, policy: GuardrailPolicy) -> None:
    names = sorted({qualified.split(".", 1)[1] for qualified in policy.blocked_columns})
    if not names:
        return
    pattern = re.compile(r"\b(" + "|".join(re.escape(name) for name in names) + r")\b", re.IGNORECASE)
    match = pattern.search(probe)
    if match:
        found = match.group(0)
        raise GuardrailViolation(
            f"Query blocked by guardrails: {found} is a sensitive column and cannot be read."
        )


def _compile(statement: str, policy: GuardrailPolicy) -> None:
    """Prepare the statement so the authorizer sees SELECT *, aliases, and views."""
    conn = _connect()
    try:
        _install(conn, policy)
        try:
            conn.execute(f"EXPLAIN {statement}")
        except sqlite3.Error as exc:
            raise GuardrailViolation(_explain_sqlite_error(exc, policy)) from exc
    finally:
        conn.close()


def _install(conn: sqlite3.Connection, policy: GuardrailPolicy) -> None:
    if policy.enforce:
        conn.set_authorizer(_authorizer(policy))


def _authorizer(policy: GuardrailPolicy):
    allowed_tables = policy.allowed_tables
    allowed_columns = policy.allowed_columns
    blocked = policy.blocked_columns

    def authorize(action: int, arg1, arg2, _db, _source) -> int:
        if action in _WRITE_ACTIONS:
            return sqlite3.SQLITE_DENY
        if action == sqlite3.SQLITE_FUNCTION:
            name = (arg2 or arg1 or "").lower()
            if name in _DENIED_FUNCTIONS:
                return sqlite3.SQLITE_DENY
            return sqlite3.SQLITE_OK
        if action != sqlite3.SQLITE_READ:
            return sqlite3.SQLITE_OK
        table = (arg1 or "").lower()
        if not table:
            return sqlite3.SQLITE_OK
        if table in _CATALOG_TABLES:
            return sqlite3.SQLITE_DENY
        if table not in allowed_tables:
            # A name that is not a real schema object is a CTE or subquery alias.
            # Objects that exist but are off the allow-list stay denied.
            if table in policy.database_objects:
                return sqlite3.SQLITE_DENY
            return sqlite3.SQLITE_OK
        column = (arg2 or "").lower()
        if not column:
            return sqlite3.SQLITE_OK
        qualified = f"{table}.{column}"
        if qualified in blocked or qualified not in allowed_columns:
            return sqlite3.SQLITE_DENY
        return sqlite3.SQLITE_OK

    return authorize


def _blocked_names_for(table: str, policy: GuardrailPolicy) -> set[str]:
    prefix = table.lower() + "."
    return {qualified.split(".", 1)[1] for qualified in policy.blocked_columns if qualified.startswith(prefix)}


def _database_objects() -> frozenset[str]:
    """Names that exist in the database, so a CTE is not mistaken for one of them."""
    if not DB_PATH.is_file():
        return frozenset()
    conn = _connect()
    try:
        rows = conn.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type IN ('table', 'view')
            """
        ).fetchall()
    finally:
        conn.close()
    return frozenset(row["name"].lower() for row in rows)


def _connect() -> sqlite3.Connection:
    if not DB_PATH.is_file():
        raise GuardrailViolation(f"Database not found at {DB_PATH}. Run python db/seed_data.py first.")
    uri = f"{DB_PATH.resolve().as_uri()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA query_only = ON")
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _explain_sqlite_error(exc: sqlite3.Error, policy: GuardrailPolicy) -> str:
    message = str(exc)
    lowered = message.lower()
    if "interrupt" in lowered or "abort" in lowered:
        return f"Query timed out after {policy.timeout_seconds:g} seconds."
    if "readonly" in lowered or "query_only" in lowered or "attempt to write" in lowered:
        return "Only SELECT statements are allowed."
    if "prohibited" in lowered or lowered.strip() == "not authorized":
        return f"Query blocked by guardrails: {message}"
    return f"Query failed: {message}"


def _interrupt_after(deadline: float):
    def handler() -> int:
        if time.monotonic() >= deadline:
            return 1
        return 0

    return handler


def _json_cell(value):
    if isinstance(value, str):
        return sanitize_untrusted(value)
    if value is None or isinstance(value, (int, float, bool)):
        return value
    if isinstance(value, bytes):
        return sanitize_untrusted(value.decode("utf-8", errors="replace"))
    return sanitize_untrusted(str(value))


def _table_columns(sql: str) -> dict[str, list[str]]:
    tables: dict[str, list[str]] = {}
    for match in re.finditer(r"CREATE\s+TABLE\s+(\w+)\s*\(", sql, re.IGNORECASE):
        name = match.group(1).lower()
        body = _balanced_body(sql, match.end())
        body = re.sub(r"--.*?$", "", body, flags=re.MULTILINE)
        columns: list[str] = []
        for part in _split_commas(body):
            piece = part.strip()
            if not piece or _SKIP_CLAUSE.match(piece):
                continue
            ident = re.match(r"([A-Za-z_][A-Za-z0-9_]*)", piece)
            if ident:
                columns.append(ident.group(1).lower())
        tables[name] = columns
    return tables


def _balanced_body(sql: str, start: int) -> str:
    depth = 1
    index = start
    while index < len(sql) and depth:
        char = sql[index]
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
        index += 1
    return sql[start : index - 1]


def _split_commas(text: str) -> list[str]:
    parts: list[str] = []
    depth = 0
    start = 0
    for index, char in enumerate(text):
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
        elif char == "," and depth == 0:
            parts.append(text[start:index])
            start = index + 1
    parts.append(text[start:])
    return parts


def _strip_trailing_semicolons(text: str) -> str:
    text = text.strip()
    while text.endswith(";"):
        text = text[:-1].rstrip()
    return text


def _scan(sql: str) -> tuple[str, str]:
    cleaned: list[str] = []
    masked: list[str] = []
    index = 0
    length = len(sql)
    while index < length:
        char = sql[index]
        nxt = sql[index + 1] if index + 1 < length else ""
        if char == "-" and nxt == "-":
            index += 2
            while index < length and sql[index] != "\n":
                index += 1
            cleaned.append(" ")
            masked.append(" ")
            continue
        if char == "/" and nxt == "*":
            index += 2
            while index + 1 < length and not (sql[index] == "*" and sql[index + 1] == "/"):
                index += 1
            index = min(length, index + 2)
            cleaned.append(" ")
            masked.append(" ")
            continue
        if char in {"'", '"'}:
            quote = char
            end = index + 1
            while end < length:
                if sql[end] == quote:
                    if end + 1 < length and sql[end + 1] == quote:
                        end += 2
                        continue
                    end += 1
                    break
                end += 1
            cleaned.append(sql[index:end])
            masked.append("''" if quote == "'" else '""')
            index = end
            continue
        cleaned.append(char)
        masked.append(char)
        index += 1
    return "".join(cleaned), "".join(masked)


POLICY = load_policy()
