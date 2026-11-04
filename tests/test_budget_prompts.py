"""Budget arithmetic feedback and equal information for group planners."""
import json
from pathlib import Path

import pytest

from tripbot.planning.prompts import (
    setup_a_prompt, mediator_prompt, friend_prompt, repair_budget_summary, revision_prompt,
)
from tripbot.schemas import Profile, load_places, load_travel_times

ROOT = Path(__file__).resolve().parents[1]


def inputs():
    profiles = {"Amy": Profile(likes=["food"], hard_limits=[], budget=100),
                "Ben": Profile(likes=["culture"], hard_limits=[], budget=23)}
    return profiles, load_places(ROOT / "data/places.json"), load_travel_times(ROOT / "data/travel_times.json")


def plan(*identifiers):
    return json.dumps({"days": [{"day": i + 1, "items": [
        {"place_id": identifier, "start": "10:00", "end": "11:00"}]} for i, identifier in enumerate(identifiers)]})


def test_group_budget_information_is_identical_and_friend_visibility_is_preserved():
    profiles, places, travel = inputs()
    config = {"days": 2, "day_start": "07:00", "day_end": "23:00",
              "paths": {"tags": str(ROOT / "data/tags.json")}}
    a = setup_a_prompt(profiles, places, travel, config)
    c = mediator_prompt(profiles, {}, places, travel, config)
    for text in (a, c):
        assert "Effective group budget: 23 per person for the ENTIRE trip, not per day." in text
        assert "not their sum or average" in text
        assert "Do not divide that sum by the number of friends" in text
    friend = friend_prompt("Amy", profiles["Amy"], places, travel, config)
    assert "Effective this friend budget: 100" in friend
    assert "Effective group budget" not in friend
    assert "Ben" not in friend


def test_budget_feedback_sums_all_visits_across_days():
    profiles, places, _ = inputs()
    # 8 + 8 + 4 + 4 = 24, matching the observed v3 failure.
    feedback = repair_budget_summary(plan("p01", "p10", "p14", "p11"), profiles, places)
    assert feedback == {"group_budget_per_person_whole_trip": 23,
                        "previous_total_cost_per_person": 24,
                        "over_budget_by": 1, "remaining_budget": -1}
    # Repeated visits are invalid but their incurred costs must not disappear.
    assert repair_budget_summary(plan("p01", "p01"), profiles, places)["previous_total_cost_per_person"] == 16


@pytest.mark.parametrize("previous", ["not json", "{}", '{"days":"bad"}'])
def test_unparseable_total_is_unknown(previous):
    profiles, places, _ = inputs()
    assert repair_budget_summary(previous, profiles, places)["previous_total_cost_per_person"] is None


def test_unknown_place_cost_is_not_treated_as_free():
    profiles, places, _ = inputs()
    feedback = repair_budget_summary(plan("p01", "unknown"), profiles, places)
    assert feedback["previous_total_cost_per_person"] is None
    assert feedback["known_cost_subtotal"] == 8
    assert feedback["unknown_place_ids"] == ["unknown"]


def test_fenced_plan_feedback_and_all_constraints_reminder():
    profiles, places, _ = inputs()
    feedback = repair_budget_summary("```json\n" + plan("p01") + "\n```", profiles, places)
    prompt = revision_prompt("base instructions", "previous", [], budget_feedback=feedback)
    assert feedback["previous_total_cost_per_person"] == 8
    assert '"group_budget_per_person_whole_trip": 23' in prompt
    assert '"previous_total_cost_per_person": 8' in prompt
    assert "ALL original constraints" in prompt
    assert "dropping required days or activities" in prompt
