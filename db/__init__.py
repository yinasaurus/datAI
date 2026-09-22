"""Northline State University sample database.

The generated SQLite file is created by ``python db/seed_data.py``.
Foreign keys are off by default in SQLite; always open the file with ``connect()``.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

AS_OF_DATE = "2026-09-22"
UNIVERSITY_NAME = "Northline State University"
# Columns the guardrail layer refuses to return.
SENSITIVE_COLUMNS = ("students.ssn", "faculty.salary")
DB_PATH = Path(__file__).resolve().parent / "university.db"
SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"


def connect(db_path: str | Path | None = None) -> sqlite3.Connection:
    """Open the database with foreign keys enforced and rows accessible by column name."""
    path = Path(db_path) if db_path is not None else DB_PATH
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn
