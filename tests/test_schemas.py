"""Tests for the pydantic models and travel lookup."""

import pytest
from pydantic import ValidationError

from tripbot.schemas import (
    Fairness,
    Place,
    Plan,
    Profile,
    Report,
    Scenario,
    TagCatalog,
    TravelTimes,
    Violation,
    place_fits,
    travel_minutes,
)


def _place(**overrides: object) -> Place:
    base: dict[str, object] = {
        "id": "p01",
        "name": "PLACEHOLDER 01",
        "tags": ["food"],
        "cost": 10,
        "opens": "10:00",
        "closes": "18:00",
        "area": "centre",
        "duration_min": 60,
        "source": "TODO",
        "verified": False,
    }
    base.update(overrides)
    return Place.model_validate(base)


def test_place_rejects_a_window_shorter_than_the_visit() -> None:
    with pytest.raises(ValidationError):
        _place(opens="10:00", closes="10:30", duration_min=60)


def test_place_rejects_closes_before_opens() -> None:
    with pytest.raises(ValidationError):
        _place(opens="18:00", closes="10:00")


def test_tag_catalog_rejects_an_unknown_forbidden_tag() -> None:
    with pytest.raises(ValidationError, match="unknown tag"):
        TagCatalog.model_validate(
            {
                "tags": ["food"],
                "hard_limits": {"no_temples": {"type": "forbid_tag", "tag": "temples"}},
            }
        )


def test_travel_minutes_are_symmetric() -> None:
    table = TravelTimes.model_validate(
        {
            "areas": ["centre", "north", "east"],
            "minutes": {"centre": {"north": 20, "east": 35}, "north": {"east": 30}},
            "same_area_minutes": 5,
        }
    )

    assert travel_minutes(table, "centre", "north") == 20
    assert travel_minutes(table, "north", "centre") == 20
    assert table.travel_minutes("east", "north") == 30
    assert travel_minutes(table, "centre", "centre") == 5


def test_travel_times_reject_a_missing_pair() -> None:
    with pytest.raises(ValidationError, match="missing travel pairs"):
        TravelTimes.model_validate(
            {
                "areas": ["centre", "north"],
                "minutes": {},
                "same_area_minutes": 5,
            }
        )


def test_travel_times_reject_asymmetric_minutes() -> None:
    with pytest.raises(ValidationError, match="asymmetric"):
        TravelTimes.model_validate(
            {
                "areas": ["centre", "north"],
                "minutes": {"centre": {"north": 20}, "north": {"centre": 40}},
                "same_area_minutes": 5,
            }
        )


def test_scenario_example_from_the_spec() -> None:
    scenario = Scenario.model_validate(
        {
            "id": "s_007",
            "split": "heldout",
            "days": 2,
            "n_friends": 3,
            "conflict": "strong",
            "budget": "tight",
            "friends": {
                "Amy": {"likes": ["food"], "hard_limits": [], "budget": 120},
                "Ben": {"likes": ["hiking"], "hard_limits": ["no_temples"], "budget": 80},
                "Cara": {
                    "likes": ["shopping"],
                    "hard_limits": ["no_early_mornings"],
                    "budget": 100,
                },
            },
        }
    )

    assert scenario.friends["Ben"].budget == 80
    assert isinstance(scenario.friends["Amy"], Profile)


def test_scenario_rejects_a_friend_count_mismatch() -> None:
    with pytest.raises(ValidationError, match="n_friends"):
        Scenario.model_validate(
            {
                "id": "s_000",
                "split": "dev",
                "days": 1,
                "n_friends": 2,
                "conflict": "mild",
                "budget": "loose",
                "friends": {"Amy": {"likes": ["food"], "hard_limits": [], "budget": 50}},
            }
        )


def test_plan_example_from_the_spec() -> None:
    plan = Plan.model_validate(
        {"days": [{"day": 1, "items": [{"place_id": "p01", "start": "18:00", "end": "19:30"}]}]}
    )

    assert plan.days[0].items[0].place_id == "p01"


def test_plan_item_rejects_an_end_at_or_before_the_start() -> None:
    with pytest.raises(ValidationError, match="end must be after start"):
        Plan.model_validate(
            {"days": [{"day": 1, "items": [{"place_id": "p01", "start": "18:00", "end": "18:00"}]}]}
        )


def test_report_task_success_follows_feasibility_and_hard_limits() -> None:
    report = Report(
        feasible=True,
        violations=[],
        hard_limit_satisfaction=1.0,
        per_friend_satisfaction={"Amy": 1.0, "Ben": 0.5},
        fairness=Fairness(min=0.5, gap=0.5, jain=0.9),
        task_success=True,
    )

    assert report.task_success is True
    with pytest.raises(ValidationError, match="task_success"):
        Report(
            feasible=False,
            violations=[Violation(type="over_budget", detail="Amy")],
            hard_limit_satisfaction=1.0,
            per_friend_satisfaction={"Amy": 1.0},
            fairness=Fairness(min=1.0, gap=0.0, jain=1.0),
            task_success=True,
        )


def test_place_fits_respects_the_day_window() -> None:
    early = _place(opens="07:00", closes="09:30", duration_min=60)
    daytime = _place(opens="10:00", closes="18:00", duration_min=60)

    assert place_fits(early, "07:00", "23:00") is True
    assert place_fits(early, "10:00", "23:00") is False
    assert place_fits(daytime, "10:00", "23:00") is True
