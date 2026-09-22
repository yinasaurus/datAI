"""Neutralize instruction-like text that arrives inside database cells.

Row values are data. A cell can still contain text that looks like a prompt,
a role tag, or a fence that tries to escape the data block. The sanitizer
redacts those phrases before the text is shown to the model.
"""

from __future__ import annotations

import re

_INVISIBLE = re.compile(r"[\u200b-\u200f\u202a-\u202e\u2060-\u2069\ufeff]")

# Phrases that try to override the system prompt or impersonate a role.
# Ordinary words such as "assistant professor" and "operating system" do not match.
_INJECTION = re.compile(
    r"(?i)("
    r"ignore\s+(all\s+|any\s+)?(previous|prior|above|earlier)\s+(instructions|prompts|rules|guidelines)"
    r"|disregard\s+(all\s+|any\s+|your\s+|the\s+)?(previous\s+|prior\s+)?(instructions|rules|guidelines|policy|guardrails)"
    r"|forget\s+everything"
    r"|forget\s+(all\s+|your\s+)?(previous\s+|prior\s+)?(instructions|rules|guidelines)"
    r"|you\s+are\s+now"
    r"|new\s+instructions"
    r"|system\s+prompt"
    r"|do\s+not\s+follow\s+(the\s+)?(previous|prior|above|your)\s+(instructions|rules)"
    r"|<\s*/?\s*(system|assistant|user|instructions|prompt)\b[^>]*>"
    r"|<\|im_start\|>|<\|im_end\|>|<\|system\|>|<\|user\|>|<\|assistant\|>"
    r")"
)

_FILTERED = "[filtered]"


def sanitize_untrusted(value: str) -> str:
    """Return cell text with prompt-injection phrases redacted."""
    text = _INVISIBLE.sub("", value).replace("\x00", "")
    text = _INJECTION.sub(_FILTERED, text)
    text = text.replace("```", "'''").replace("<|", "< |")
    return text


def sanitize_rows(rows: list) -> list:
    """Sanitize every string in a list of row values. Other types are unchanged."""
    return [_sanitize_row(row) for row in rows]


def _sanitize_row(row):
    if isinstance(row, dict):
        return {key: _sanitize_cell(value) for key, value in row.items()}
    if isinstance(row, (list, tuple)):
        return [_sanitize_cell(value) for value in row]
    return _sanitize_cell(row)


def _sanitize_cell(value):
    if isinstance(value, str):
        return sanitize_untrusted(value)
    return value
