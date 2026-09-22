"""Chat model used to write SQL and to summarize rows.

The default client is OpenAI-compatible. Set OPENAI_API_KEY, and optionally
OPENAI_MODEL (default gpt-4o-mini) and OPENAI_BASE_URL.
"""

from __future__ import annotations

import os
import re
from typing import Protocol


class ChatModel(Protocol):
    def complete(self, *, system: str, user: str) -> str:
        """Return the assistant message for one system prompt and one user message."""


class OpenAIChat:
    """Minimal chat client. The key is read from the environment, not from code."""

    def __init__(self, model: str | None = None) -> None:
        if not os.environ.get("OPENAI_API_KEY"):
            raise RuntimeError(
                "OPENAI_API_KEY is not set. The agent uses an OpenAI-compatible chat model "
                "to write SQL and summarize rows. Set OPENAI_API_KEY, and optionally "
                "OPENAI_MODEL and OPENAI_BASE_URL."
            )
        self.model = model or os.environ.get("OPENAI_MODEL", "gpt-4o-mini")

    def complete(self, *, system: str, user: str) -> str:
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise RuntimeError("Install the openai package to use OpenAIChat.") from exc
        client = OpenAI()
        response = client.chat.completions.create(
            model=self.model,
            temperature=0,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        content = response.choices[0].message.content
        if content is None:
            return ""
        if isinstance(content, str):
            return content.strip()
        pieces: list[str] = []
        for block in content:
            text = getattr(block, "text", None)
            if isinstance(text, str):
                pieces.append(text)
        return "".join(pieces).strip()


def extract_sql(message: str) -> str:
    """Pull a single SQL statement out of a model reply."""
    text = message.strip()
    if not text:
        return ""
    fenced = re.search(r"```(?:sql)?\s*(.*?)```", text, flags=re.IGNORECASE | re.DOTALL)
    if fenced:
        text = fenced.group(1).strip()
    match = re.search(r"(?is)\b(with|select)\b\s.*", text)
    if not match:
        return ""
    statement = match.group(0).strip()
    statement = re.sub(r";\s*$", "", statement).strip()
    return statement
