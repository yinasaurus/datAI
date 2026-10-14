"""Setup C tests. The fake client returns canned plans and does not use the network."""

from pathlib import Path
from types import SimpleNamespace

import pytest

from tripbot.planning.registry import make_plan
from tripbot.planning.setup_c import proposal_calls
from tripbot.schemas import Place, Profile, TravelTimes

ROOT = Path(__file__).resolve().parents[1]

GOOD = '{"days":[{"day":1,"items":[{"place_id":"food","start":"10:00","end":"11:00"}]}]}'
BEN_PLAN = '{"days":[{"day":1,"items":[{"place_id":"food","start":"12:00","end":"13:00"}]}]}'
BAD = '{"days":[{"day":1,"items":[{"place_id":"food","start":"08:00","end":"09:00"}]}]}'


class FakeClient:
    def __init__(self, texts: list[str]) -> None:
        self._texts = list(texts)
        self.calls: list[dict[str, object]] = []
        self.models = self

    def generate_content(self, *, model: str, contents: str, config: object) -> SimpleNamespace:
        self.calls.append({"model": model, "contents": contents, "config": config})
        usage = SimpleNamespace(prompt_token_count=8, candidates_token_count=9)
        return SimpleNamespace(text=self._texts.pop(0), usage_metadata=usage)


def _config(tmp_path: Path, *, rounds: int, revisions: int) -> dict[str, object]:
    return {
        "model": "test-model",
        "temperature": 0,
        "seed": 42,
        "cache": False,
        "days": 1,
        "negotiation_rounds": rounds,
        "max_revisions": revisions,
        "day_start": "07:00",
        "day_end": "23:00",
        "paths": {
            "tags": str(ROOT / "data" / "tags.json"),
            "llm_log": str(tmp_path / "llm_calls.jsonl"),
        },
    }


def _places() -> tuple[list[Place], TravelTimes]:
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
    return places, travel


def _friends() -> dict[str, Profile]:
    return {
        "Amy": Profile(likes=["food"], hard_limits=[], budget=100),
        "Ben": Profile(likes=["hiking-secret"], hard_limits=[], budget=100),
        "Cara": Profile(likes=["shopping"], hard_limits=[], budget=100),
    }


def test_three_friends_and_two_rounds_make_ten_calls(tmp_path: Path) -> None:
    places, travel = _places()
    expected = proposal_calls(3, 2)
    client = FakeClient([GOOD] * expected)

    result = make_plan("C", _friends(), places, travel, _config(tmp_path, rounds=2, revisions=3), client=client)

    assert expected == 10
    assert result.llm_calls == expected
    assert result.attempts == expected
    assert result.tokens_in == 8 * expected
    assert result.tokens_out == 9 * expected
    assert result.seconds == pytest.approx(sum(step["seconds"] for step in result.trace))
    assert len(result.trace) == expected
    assert [step["step"] for step in result.trace].count("friend") == 9
    assert [step["round"] for step in result.trace if step["step"] == "friend"] == [0, 0, 0, 1, 1, 1, 2, 2, 2]
    assert result.trace[-1]["step"] == "mediator"
    assert result.trace[-1]["violations"] == []
    assert result.plan is not None
    assert result.plan.days[0].items[0].start == "10:00"


def test_round_zero_hides_other_profiles_and_later_rounds_show_proposals(tmp_path: Path) -> None:
    places, travel = _places()
    profiles = {
        "Amy": Profile(likes=["food"], hard_limits=[], budget=100),
        "Ben": Profile(likes=["hiking-secret"], hard_limits=[], budget=100),
    }
    client = FakeClient([GOOD, BEN_PLAN, GOOD, GOOD, GOOD])

    result = make_plan("C", profiles, places, travel, _config(tmp_path, rounds=1, revisions=0), client=client)

    amy_round_0 = str(client.calls[0]["contents"])
    amy_round_1 = str(client.calls[2]["contents"])
    mediator = str(client.calls[4]["contents"])
    assert "hiking-secret" not in amy_round_0
    assert "12:00" not in amy_round_0
    assert "Other friends" not in amy_round_0
    assert "12:00" in amy_round_1
    assert "hiking-secret" not in amy_round_1
    assert "hiking-secret" in mediator
    assert result.llm_calls == proposal_calls(2, 1)
    assert "You represent one friend" in str(client.calls[0]["config"].system_instruction)


def test_checker_revision_adds_one_call_after_the_merge(tmp_path: Path) -> None:
    places, travel = _places()
    profiles = {"Amy": Profile(likes=["food"], hard_limits=[], budget=100)}
    client = FakeClient([GOOD, BAD, GOOD])

    result = make_plan("C", profiles, places, travel, _config(tmp_path, rounds=0, revisions=1), client=client)

    assert result.llm_calls == proposal_calls(1, 0) + 1
    assert [step["step"] for step in result.trace] == ["friend", "mediator", "revision"]
    assert result.trace[1]["violations"][0]["type"] == "closed"
    assert result.trace[2]["violations"] == []
    assert "closed" in str(client.calls[2]["contents"])
    assert result.plan is not None
    assert result.plan.days[0].items[0].start == "10:00"
