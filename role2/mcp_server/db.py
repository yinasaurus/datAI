"""Open PostgreSQL and turn a failed statement into a readable error.

Role 3 owns the read-only role, the timeout, and the row limit inside the
harness. This module is the plain executor the harness allows a query to reach.
"""

from __future__ import annotations

import os
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID


class DatabaseError(Exception):
    """A connection or SQL failure the agent is allowed to read."""


def execute_query(sql: str) -> tuple[list[str], list[list[object]]]:
    """Run ``sql`` and return column names plus rows. Raises ``DatabaseError``."""
    url = os.environ.get("DATABASE_URL", "").strip()
    if not url:
        raise DatabaseError(
            "DATABASE_URL is not set. Copy role2/.env.example to role2/.env and start Docker."
        )
    try:
        import psycopg
    except ImportError as exc:
        raise DatabaseError("psycopg is not installed. See role2/requirements.txt.") from exc

    try:
        with psycopg.connect(url, connect_timeout=5) as conn:
            with conn.cursor() as cursor:
                cursor.execute(sql)
                if cursor.description is None:
                    raise DatabaseError(
                        "The statement returned no result set. The agent can only answer a SELECT."
                    )
                columns = [column.name for column in cursor.description]
                raw_rows = cursor.fetchall()
    except DatabaseError:
        raise
    except Exception as exc:
        # psycopg already phrases these as "column x does not exist" and similar.
        raise DatabaseError(str(exc).strip()) from exc

    rows = [[_cell(value) for value in row] for row in raw_rows]
    return columns, rows


def _cell(value: object) -> object:
    """Make one cell safe to put in JSON."""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, UUID):
        return str(value)
    return str(value)
