"""Chat handling tests. The model client is fake and make_plan is stubbed."""

import asyncio
import json
import logging
from pathlib import Path
from types import SimpleNamespace

import pytest

from tripbot.bot.core import TELEGRAM_LIMIT, handle_message, split_reply
from tripbot.bot.guard_adapter import GuardResult
from tripbot.bot.telegram_app import deliver
from tripbot.planning.registry import PlanResult
from tripbot.schemas import Plan, load_places

ROOT = Path(__file__).resolve().parents[1]
MARKER = "UNIQUE_CHAT_MARKER"
PLAN = Plan.model_validate(
    {"days": [{"day": 1, "items": [{"place_id": "p01", "start": "10:00", "end": "11:00"}]}]}
)


class FakeClient:
    def __init__(self, texts: list[str]) -> None:
        self._texts = list(texts)
        self.models = self

    def generate_content(self, *, model: str, contents: str, config: object) -> SimpleNamespace:
        usage = SimpleNamespace(prompt_token_count=3, candidates_token_count=4)
        return SimpleNamespace(text=self._texts.pop(0), usage_metadata=usage)


def _config(tmp_path: Path) -> dict[str, object]:
    return {
        "model": "test-model",
        "temperature": 0,
        "seed": 42,
        "cache": False,
        "setup": "A",
        "days": 1,
        "bot_name": "tripbot",
        "cooldown_seconds": 20,
        "guardrails": "on",
        "budget_cap": 3000,
        "day_start": "07:00",
        "day_end": "23:00",
        "paths": {
            "tags": str(ROOT / "data" / "tags.json"),
            "places": str(ROOT / "data" / "places.json"),
            "travel_times": str(ROOT / "data" / "travel_times.json"),
            "llm_log": str(tmp_path / "llm_calls.jsonl"),
            "bot_state": str(tmp_path / "bot_state.json"),
        },
    }


def _profile(likes: list[str], limits: list[str], budget: int) -> str:
    return json.dumps({"likes": likes, "hard_limits": limits, "budget": budget})


def _empty() -> str:
    return json.dumps({"likes": [], "hard_limits": [], "budget": None})


def _plan_result(*args: object, **kwargs: object) -> PlanResult:
    return PlanResult(
        plan=PLAN,
        attempts=1,
        llm_calls=1,
        tokens_in=1,
        tokens_out=1,
        seconds=0.0,
        trace=[],
    )


def _seed_two_friends(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[dict[str, object], FakeClient]:
    monkeypatch.setattr("tripbot.bot.core.make_plan", _plan_result)
    config = _config(tmp_path)
    client = FakeClient(
        [
            _profile(["food"], [], 100),
            _profile(["hiking"], ["no_temples"], 80),
        ]
    )
    assert handle_message("g1", "Amy", "I like food. Budget 100.", config, client=client) is None
    assert handle_message("g1", "Ben", "I like hiking. Budget 80.", config, client=client) is None
    return config, client


def test_ordinary_message_stays_quiet(tmp_path: Path) -> None:
    config = _config(tmp_path)
    client = FakeClient([_profile(["food"], [], 100)])

    reply = handle_message("g1", "Amy", "I like food. Budget 100.", config, client=client)

    assert reply is None
    saved = json.loads((tmp_path / "bot_state.json").read_text(encoding="utf-8"))
    assert saved["groups"]["g1"]["profiles"]["Amy"]["likes"] == ["food"]


def test_plan_reply_uses_the_plan_and_hides_chat_text(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config, client = _seed_two_friends(tmp_path, monkeypatch)
    client._texts.append(_empty())

    reply = handle_message("g1", "Amy", f"/plan {MARKER}", config, client=client)

    assert reply is not None
    assert "Day 1" in reply
    first = load_places(ROOT / "data" / "places.json")[0]
    assert f"10:00-11:00 {first.name}" in reply
    assert f"Cost per person: {first.cost}" in reply
    assert "Violations: none" in reply
    assert MARKER not in reply
    assert len(reply) <= TELEGRAM_LIMIT


def test_cooldown_suppresses_a_second_plan(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    clock = {"now": 1_000.0}
    monkeypatch.setattr("tripbot.bot.core.time.time", lambda: clock["now"])
    config, client = _seed_two_friends(tmp_path, monkeypatch)
    client._texts.extend([_empty(), _empty(), _empty()])

    first = handle_message("g1", "Amy", "/plan", config, client=client)
    clock["now"] = 1_010.0
    second = handle_message("g1", "Ben", "/itinerary", config, client=client)
    clock["now"] = 1_021.0
    third = handle_message("g1", "Amy", "tripbot, please make a schedule", config, client=client)

    assert first is not None
    assert second is None
    assert third is not None


def test_one_friend_is_asked_for_more_preferences(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("tripbot.bot.core.make_plan", _plan_result)
    config = _config(tmp_path)
    client = FakeClient([_profile(["food"], [], 100), _empty()])

    handle_message("g1", "Amy", "I like food. Budget 100.", config, client=client)
    reply = handle_message("g1", "Amy", "/plan", config, client=client)

    assert reply is not None
    assert "at least two friends" in reply


def test_profiles_lists_the_group(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config, client = _seed_two_friends(tmp_path, monkeypatch)
    client._texts.append(_empty())

    reply = handle_message("g1", "Cara", "/profiles", config, client=client)

    assert reply is not None
    assert "Amy:" in reply
    assert "Ben:" in reply
    assert "no_temples" in reply


def test_confirm_without_a_plan(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def fail_book(plan: object, confirmed: bool) -> dict[str, bool]:
        raise AssertionError("mock_book should not run")

    monkeypatch.setattr("tripbot.bot.core.mock_book", fail_book)
    config = _config(tmp_path)
    client = FakeClient([_empty()])

    reply = handle_message("g1", "Amy", "/confirm", config, client=client)

    assert reply is not None
    assert "nothing to confirm" in reply.lower()


def test_guard_block_prevents_the_plan_reply(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def gate(action_type: str, payload: dict, context: dict) -> GuardResult:
        if action_type == "reply" and "Cost per person" in str(payload.get("text")):
            return GuardResult(False, "blocked")
        return GuardResult(True, "ok")

    monkeypatch.setattr("tripbot.bot.core.check_action", gate)
    config, client = _seed_two_friends(tmp_path, monkeypatch)
    client._texts.append(_empty())

    reply = handle_message("g1", "Amy", "/plan", config, client=client)

    assert reply is None
    saved = json.loads((tmp_path / "bot_state.json").read_text(encoding="utf-8"))
    assert saved["groups"]["g1"]["latest_plan"] is None


def test_example_chat_has_three_friends_a_clash_and_a_plan_request() -> None:
    messages = json.loads((ROOT / "data" / "chats" / "example.json").read_text(encoding="utf-8"))
    text = " ".join(item["text"] for item in messages)

    assert len(messages) == 12
    assert {item["sender"] for item in messages} == {"Amy", "Ben", "Cara"}
    assert "temples" in text
    assert "no_temples" in text
    assert "/plan" in text


def test_split_reply_stays_within_the_telegram_limit() -> None:
    parts = split_reply("line\n" * 3000, limit=100)

    assert len(parts) > 1
    assert all(len(part) <= 100 for part in parts)


def test_telegram_logs_handler_errors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    def boom(*args: object, **kwargs: object) -> None:
        raise RuntimeError("planner blew up")

    monkeypatch.setattr("tripbot.bot.telegram_app.handle_message", boom)

    class Message:
        text = "hello"

        async def reply_text(self, text: str) -> None:
            raise AssertionError("no reply should be sent")

    with caplog.at_level(logging.ERROR):
        asyncio.run(deliver(Message(), "g1", "Amy", "hello", _config(tmp_path)))

    assert any("telegram update failed" in record.message for record in caplog.records)
