"""LLM client tests. The fake client never opens a network connection."""

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from google.genai.errors import ClientError

from tripbot.llm import call_llm
from tripbot.planning.prompts import PROMPT_VERSION

ROOT = Path(__file__).resolve().parents[1]


class FakeClient:
    """Stand-in for google.genai.Client."""

    def __init__(self, responses: list[SimpleNamespace], errors: list[Exception] | None = None) -> None:
        self._responses = list(responses)
        self._errors = list(errors or [])
        self.calls: list[dict[str, object]] = []
        self.models = self

    def generate_content(self, *, model: str, contents: str, config: object) -> SimpleNamespace:
        self.calls.append({"model": model, "contents": contents, "config": config})
        if self._errors:
            raise self._errors.pop(0)
        return self._responses.pop(0)


def _reply(text: str, incoming: int = 11, outgoing: int = 7) -> SimpleNamespace:
    usage = SimpleNamespace(prompt_token_count=incoming, candidates_token_count=outgoing)
    return SimpleNamespace(text=text, usage_metadata=usage)


def _config(tmp_path: Path, **overrides: object) -> dict[str, object]:
    config: dict[str, object] = {
        "model": "test-model",
        "temperature": 0,
        "seed": 42,
        "cache": False,
        "paths": {"llm_log": str(tmp_path / "llm_calls.jsonl")},
    }
    config.update(overrides)
    return config


def _rate_limit() -> ClientError:
    return ClientError(
        429,
        {"error": {"code": 429, "message": "slow down", "status": "RESOURCE_EXHAUSTED"}},
    )


def test_call_reads_model_temperature_seed_and_json_mode(tmp_path: Path) -> None:
    client = FakeClient([_reply('{"days": []}')])

    result = call_llm("system", "prompt", _config(tmp_path), True, client=client)

    sent = client.calls[0]
    request = sent["config"]
    assert sent["model"] == "test-model"
    assert request.temperature == 0
    assert request.seed == 42
    assert request.system_instruction == "system"
    assert request.response_mime_type == "application/json"
    assert result.text == '{"days": []}'
    assert result.tokens_in == 11
    assert result.tokens_out == 7
    assert result.cached is False
    log = json.loads((tmp_path / "llm_calls.jsonl").read_text(encoding="utf-8"))
    assert log["model"] == "test-model"
    assert log["prompt_version"] == PROMPT_VERSION
    assert log["attempts"] == 1
    assert log["error"] is None


def test_retry_uses_exponential_backoff_then_returns(tmp_path: Path) -> None:
    client = FakeClient([_reply("ok")], errors=[_rate_limit(), _rate_limit()])
    delays: list[float] = []

    result = call_llm(
        "system",
        "prompt",
        _config(tmp_path),
        False,
        client=client,
        sleeper=delays.append,
    )

    assert delays == [1.0, 2.0]
    assert result.text == "ok"
    assert len(client.calls) == 3
    assert client.calls[0]["config"].response_mime_type is None


def test_client_error_is_not_retried(tmp_path: Path) -> None:
    client = FakeClient([], errors=[ClientError(400, {"error": {"code": 400, "message": "bad", "status": "INVALID"}})])
    delays: list[float] = []

    with pytest.raises(ClientError):
        call_llm("system", "prompt", _config(tmp_path), True, client=client, sleeper=delays.append)

    assert delays == []
    assert len(client.calls) == 1
    log = json.loads((tmp_path / "llm_calls.jsonl").read_text(encoding="utf-8"))
    assert log["error"] is not None
    assert log["attempts"] == 1


def test_cache_hit_skips_the_client_and_ignores_seed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    client = FakeClient([_reply("cached-text", incoming=3, outgoing=4)])
    config = _config(tmp_path, cache=True)

    first = call_llm("system", "prompt", config, True, client=client)
    config["seed"] = 99
    second = call_llm("system", "prompt", config, True, client=client)

    assert first.cached is False
    assert second.cached is True
    assert second.text == "cached-text"
    assert second.tokens_in == 3
    assert len(client.calls) == 1
    lines = (tmp_path / "llm_calls.jsonl").read_text(encoding="utf-8").splitlines()
    assert json.loads(lines[1])["cached"] is True
    assert json.loads(lines[1])["attempts"] == 0


def test_temperature_change_misses_the_cache(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    client = FakeClient([_reply("one"), _reply("two")])
    config = _config(tmp_path, cache=True)

    call_llm("system", "prompt", config, True, client=client)
    config["temperature"] = 1
    second = call_llm("system", "prompt", config, True, client=client)

    assert second.cached is False
    assert len(client.calls) == 2
