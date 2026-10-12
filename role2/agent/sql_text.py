"""Pull a SQL statement out of a model reply."""

from __future__ import annotations

import re

_FENCE = re.compile(r"```(?:sql)?\s*(.*?)```", re.IGNORECASE | re.DOTALL)
_STATEMENT = re.compile(r"(?is)\b(?:with|select)\b.*")


def extract_sql(text: str) -> str:
    """Return the SQL from a fence or from the first WITH/SELECT. Empty if none."""
    if not isinstance(text, str):
        return ""
    fenced = _FENCE.search(text)
    if fenced:
        return fenced.group(1).strip()
    match = _STATEMENT.search(text)
    if match:
        return match.group(0).strip().rstrip("`").strip()
    return ""
