"""Rows written to results/runs.jsonl carry the prompt version."""

import json
from pathlib import Path

from tripbot.eval.record import append_run
from tripbot.planning.prompts import PROMPT_VERSION


def test_run_row_records_prompt_version(tmp_path: Path) -> None:
    path = tmp_path / "results" / "runs.jsonl"

    append_run(path, {"scenario_id": "s_001", "setup": "A", "prompt_version": "stale"})

    row = json.loads(path.read_text(encoding="utf-8").splitlines()[0])
    assert row["scenario_id"] == "s_001"
    assert row["setup"] == "A"
    assert row["prompt_version"] == PROMPT_VERSION
