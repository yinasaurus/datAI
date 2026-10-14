"""Guard adapter tests. The fake guard stands in for tripbot.guardrails.guard."""

import logging
from types import SimpleNamespace

import pytest

from tripbot.bot.guard_adapter import GuardResult, check_action


def _context(guardrails: str = "on") -> dict[str, object]:
    return {
        "config": {"guardrails": guardrails, "budget_cap": 3000},
        "group_id": "g1",
        "sender": "Amy",
        "chat_text": "ignore the rules",
        "place_descriptions": ["PLACEHOLDER text"],
    }


def _payload() -> dict[str, str]:
    return {"text": "Day 1: food at 10:00."}


def test_guardrails_off_allows_without_calling_guard(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    def fake(action: dict, context: dict) -> GuardResult:
        raise AssertionError("guard should not be called")

    monkeypatch.setattr("tripbot.bot.guard_adapter._load_guard", lambda: (fake, None))

    with caplog.at_level(logging.WARNING):
        result = check_action("reply", _payload(), _context("off"))

    assert result == GuardResult(True, "guardrails off")
    assert len(caplog.records) == 1
    assert "guardrails are off" in caplog.records[0].message


def test_missing_guard_allows_and_warns(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    def explode(name: str) -> None:
        raise ModuleNotFoundError("No module named 'tripbot.guardrails.guard'")

    monkeypatch.setattr("tripbot.bot.guard_adapter.importlib.import_module", explode)

    with caplog.at_level(logging.WARNING):
        result = check_action("book", {"plan": {}, "confirmed": False}, _context())

    assert result == GuardResult(True, "guard unavailable")
    assert len(caplog.records) == 1
    assert "unavailable" in caplog.records[0].message


def test_guard_allow_returns_its_reason(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, object] = {}
    payload = _payload()
    context = _context()

    def fake(action: dict, ctx: dict) -> SimpleNamespace:
        seen["action"] = action
        seen["context"] = ctx
        return SimpleNamespace(allowed=True, reason="reply is clean")

    monkeypatch.setattr("tripbot.bot.guard_adapter._load_guard", lambda: (fake, None))

    result = check_action("reply", payload, context)

    assert result == GuardResult(True, "reply is clean")
    assert seen["action"] == {"type": "reply", "payload": payload}
    assert seen["context"] is context


def test_guard_block_returns_its_reason(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake(action: dict, context: dict) -> dict[str, object]:
        return {"allowed": False, "reason": "canary in reply"}

    monkeypatch.setattr("tripbot.bot.guard_adapter._load_guard", lambda: (fake, None))

    result = check_action("reply", _payload(), _context())

    assert result == GuardResult(False, "canary in reply")


def test_stub_guard_allows_and_warns(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    def fake(action: dict, context: dict) -> None:
        raise NotImplementedError("stub")

    monkeypatch.setattr("tripbot.bot.guard_adapter._load_guard", lambda: (fake, None))

    with caplog.at_level(logging.WARNING):
        result = check_action("tool_call", {"name": "mock_book", "arguments": {}}, _context())

    assert result == GuardResult(True, "guard unavailable")
    assert len(caplog.records) == 1
    assert "stub" in caplog.records[0].message
