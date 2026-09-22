"""Guardrails for the SQL tools.

Enforcement is on. A query must be one SELECT (WITH ... SELECT is allowed).
It may only read tables, views, and columns declared in schema.sql, and it
may not read the sensitive columns in ``db.SENSITIVE_COLUMNS``:

- students.ssn
- faculty.salary

Results are capped at 500 rows and cancelled after 5 seconds. String values
read back from the database are treated as untrusted data and scrubbed for
prompt-injection phrases before they reach the agent.
"""

from guardrails.injection import sanitize_rows, sanitize_untrusted
from guardrails.policy import (
    POLICY,
    GuardedResult,
    GuardrailPolicy,
    GuardrailViolation,
    check_query,
    ensure_visible,
    execute_read_query,
    filter_visible,
    visible_column_names,
)

__all__ = [
    "POLICY",
    "GuardedResult",
    "GuardrailPolicy",
    "GuardrailViolation",
    "check_query",
    "ensure_visible",
    "execute_read_query",
    "filter_visible",
    "sanitize_rows",
    "sanitize_untrusted",
    "visible_column_names",
]
