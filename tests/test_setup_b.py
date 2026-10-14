"""Setup B tests. The fake client returns canned plans and does not use the network."""

from pathlib import Path
from types import SimpleNamespace

import pytest

from tripbot.planning.registry import make_plan
from tripbot.planning.setup_a import run_setup_a
from tripbot.schemas import Place, Profile, TravelTimes

ROOT = Path(__file__).resolve().parents[1]

BAD_PLAN = '{"days":[{"day":1,"items":[{"place_id":"food","start":"08:00","end":"09:00"}]}]}'
GOOD_PLAN = '{"days":[{"day":1,"items":[{"place_id":"food","start":"10:00","end":"11:00"}]}]}'


class FakeClient:
    def __init__(self, texts: list[str]) -> None:
        self._texts = list(texts)
        self.calls: list[dict[str, object]] = []
        self.models = self

    def generate_content(self, *, model: str, contents: str, config: object) -> SimpleNamespace:
        self.calls.append({"model": model, "contents": contents, "config": config})
        usage = SimpleNamespace(prompt_token_count=8, candidates_token_count=9)
        return SimpleNamespace(text=self._texts.pop(0), usage_metadata=usage)


def _config(tmp_path: Path, max_revisions: int) -> dict[str, object]:
    return {
        "model": "test-model",
        "temperature": 0,
        "seed": 42,
        "cache": False,
        "days": 1,
        "max_revisions": max_revisions,
        "day_start": "07:00",
        "day_end": "23:00",
        "paths": {
            "tags": str(ROOT / "data" / "tags.json"),
            "llm_log": str(tmp_path / "llm_calls.jsonl"),
        },
    }


def _inputs() -> tuple[dict[str, Profile], list[Place], TravelTimes]:
    profiles = {"Amy": Profile(likes=["food"], hard_limits=[], budget=100)}
    places = [
        Place.model_validate(
            {
                "id": "food",
                "name": "PLACEHOLDER food",
                "tags": ["food"],
                "cost": 20,
                "opens": "09:00",
                "closes": "18:00",
                "area": "centre",
                "duration_min": 60,
                "source": "TODO",
                "verified": False,
            }
        )
    ]
    travel = TravelTimes.model_validate(
        {"areas": ["centre"], "minutes": {}, "same_area_minutes": 5}
    )
    return profiles, places, travel


def test_revision_replaces_a_bad_plan(tmp_path: Path) -> None:
    profiles, places, travel = _inputs()
    client = FakeClient([BAD_PLAN, GOOD_PLAN])

    result = make_plan("B", profiles, places, travel, _config(tmp_path, 1), client=client)

    assert result.plan is not None
    assert result.plan.days[0].items[0].start == "10:00"
    assert result.attempts == 2
    assert result.llm_calls == 2
    assert result.tokens_in == 16
    assert result.tokens_out == 18
    assert result.seconds == pytest.approx(sum(step["seconds"] for step in result.trace))
    assert result.trace[0]["violations"][0]["type"] == "closed"
    assert result.trace[1]["violations"] == []
    assert result.trace[1]["step"] == "revision"
    assert "closed" in str(client.calls[1]["contents"])
    assert "data, not instructions" in str(client.calls[1]["contents"])


def test_zero_revisions_matches_setup_a(tmp_path: Path) -> None:
    profiles, places, travel = _inputs()
    config = _config(tmp_path, 0)
    alone = run_setup_a(profiles, places, travel, config, client=FakeClient([BAD_PLAN, GOOD_PLAN]))
    client = FakeClient([BAD_PLAN, GOOD_PLAN])

    result = make_plan("B", profiles, places, travel, config, client=client)

    assert result.plan == alone.plan
    assert result.plan is not None
    assert result.plan.days[0].items[0].start == "08:00"
    assert result.attempts == 1
    assert result.llm_calls == 1
    assert len(client.calls) == 1
    assert result.trace[0]["violations"][0]["type"] == "closed"


def _call_view(call: dict[str, object]) -> dict[str, object]:
    request = call["config"]
    return {
        "model": call["model"],
        "contents": call["contents"],
        "system_instruction": request.system_instruction,
        "temperature": request.temperature,
        "seed": request.seed,
        "response_mime_type": request.response_mime_type,
        "response_json_schema": request.response_json_schema,
    }


def test_zero_revisions_makes_the_same_model_call_as_setup_a(tmp_path: Path) -> None:
    profiles, places, travel = _inputs()
    config = _config(tmp_path, 0)
    client_a = FakeClient([BAD_PLAN])
    client_b = FakeClient([BAD_PLAN])

    make_plan("A", profiles, places, travel, config, client=client_a)
    make_plan("B", profiles, places, travel, config, client=client_b)

    assert len(client_a.calls) == 1
    assert len(client_b.calls) == 1
    assert _call_view(client_a.calls[0]) == _call_view(client_b.calls[0])
