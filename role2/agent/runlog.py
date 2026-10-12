"""Append one JSON object per question so Role 4 can score latency and tokens."""

from __future__ import annotations

import json
from pathlib import Path

from interfaces.types import AnswerResult, LLMCallRecord, TokenUsage


def token_totals(calls: list[LLMCallRecord]) -> TokenUsage:
    """Sum token counts across the SQL attempts and the summary call."""
    prompt = sum(call["prompt_tokens"] for call in calls)
    completion = sum(call["completion_tokens"] for call in calls)
    total = sum(call["total_tokens"] for call in calls)
    return {"prompt": prompt, "completion": completion, "total": total}


def append_run(record: AnswerResult, path: Path) -> None:
    """Write ``record`` as one JSON line. Creates the log folder if needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")
