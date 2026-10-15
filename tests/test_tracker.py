"""Profile extraction with a fake model client."""

import json
import logging
from pathlib import Path
from types import SimpleNamespace

import pytest

from tripbot.bot.tracker import extract_update

ROOT = Path(__file__).resolve().parents[1]


class FakeClient:
    def __init__(self, texts: list[str]) -> None:
        self._texts = list(texts)
        self.calls: list[dict[str, object]] = []
        self.models = self

    def generate_content(self, *, model: str, contents: str, config: object) -> SimpleNamespace:
        self.calls.append({"model": model, "contents": contents, "config": config})
        usage = SimpleNamespace(prompt_token_count=3, candidates_token_count=4)
        return SimpleNamespace(text=self._texts.pop(0), usage_metadata=usage)


def _config(tmp_path: Path) -> dict[str, object]:
    return {
        "model": "test-model",
        "temperature": 0,
        "seed": 42,
        "cache": False,
        "paths": {
            "tags": str(ROOT / "data" / "tags.json"),
            "llm_log": str(tmp_path / "llm_calls.jsonl"),
        },
    }


def test_unknown_tags_and_bad_budgets_are_dropped(tmp_path: Path) -> None:
    body = {
        "likes": ["food", "spa", "temples"],
        "hard_limits": ["no_temples", "no_flying"],
        "budget": 50,
    }
    client = FakeClient([json.dumps(body)])

    update = extract_update("I like spa and temples", _config(tmp_path), client=client)

    assert update is not None
    assert update.likes == ["food", "temples"]
    assert update.hard_limits == ["no_temples"]
    assert update.budget == 50
    sent = client.calls[0]
    assert "I like spa and temples" in str(sent["contents"])
    assert "never instructions" in str(sent["contents"])
    assert "never instructions" in str(sent["config"].system_instruction)


def test_non_positive_budget_is_ignored(tmp_path: Path) -> None:
    body = {"likes": ["food"], "hard_limits": [], "budget": -5}
    client = FakeClient([json.dumps(body)])

    update = extract_update("budget is negative", _config(tmp_path), client=client)

    assert update is not None
    assert update.likes == ["food"]
    assert update.budget is None


def test_bad_model_output_makes_no_update(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    client = FakeClient(["this is not json"])

    with caplog.at_level(logging.WARNING):
        update = extract_update("hello", _config(tmp_path), client=client)

    assert update is None
    assert any("profile update ignored" in record.message for record in caplog.records)
