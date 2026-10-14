"""Append one experiment row to results/runs.jsonl."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from tripbot.planning.prompts import PROMPT_VERSION


def append_run(path: str | Path, row: dict[str, Any]) -> None:
    """Write one JSON line. ``prompt_version`` is always the code constant."""
    payload = dict(row)
    payload["prompt_version"] = PROMPT_VERSION
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload) + "\n")
