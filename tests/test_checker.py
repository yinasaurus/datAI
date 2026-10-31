"""Hand-made plans for every feasibility rule and the satisfaction scores."""

from pathlib import Path

import pytest

from tripbot.checker.check_plan import check_plan
from tripbot.schemas import (
    Place,
    Plan,
    PlanDay,
    PlanItem,
    Profile,
    Report,
    TravelTimes,
)

ROOT = Path(__file__).resolve().parents[1]

CONFIG = {
    "days": 1,
    "min_activities_per_day": 1,
    "day_start": "07:00",
    "day_end": "23:00",
    "paths": {"tags": str(ROOT / "data" / "tags.json")},
}

TRAVEL = TravelTimes.model_validate(
    {
        "areas": ["centre", "north"],
        "minutes": {"centre": {"north": 20}},
        "same_area_minutes": 5,
    }
)

TOUCH_TRAVEL = TravelTimes.model_validate(
    {
        "areas": ["centre", "north"],
        "minutes": {"centre": {"north": 20}},
        "same_area_minutes": 0,
    }
)


def _place(place_id: str, tags: list[str], area: str, **overrides: object) -> Place:
    base: dict[str, object] = {
        "id": place_id,
        "name": f"PLACEHOLDER {place_id}",
        "tags": tags,
        "cost": 20,
        "opens": "09:00",
        "closes": "18:00",
        "area": area,
        "duration_min": 60,
        "source": "TODO",
        "verified": False,
    }
    base.update(overrides)
    return Place.model_validate(base)


FOOD = _place("food", ["food"], "centre")
SHOP = _place("shop", ["shopping"], "north", cost=30, opens="10:00", closes="20:00")
TEMPLE = _place("temple", ["temples"], "centre", cost=15)
HIKE = _place("hike", ["hiking"], "centre", cost=10, opens="07:00", closes="12:00")
PLACES = [FOOD, SHOP, TEMPLE, HIKE]


def _plan(*days: list[tuple[str, str, str]]) -> Plan:
    return Plan(
        days=[
            PlanDay(
                day=number,
                items=[PlanItem(place_id=place_id, start=start, end=end) for place_id, start, end in items],
            )
            for number, items in enumerate(days, start=1)
        ]
    )


def _profiles(**friends: tuple[list[str], list[str], int]) -> dict[str, Profile]:
    return {
        name: Profile(likes=likes, hard_limits=limits, budget=budget)
        for name, (likes, limits, budget) in friends.items()
    }


def _types(report: Report) -> list[str]:
    return [violation.type for violation in report.violations]


def test_valid_plan_succeeds_with_full_satisfaction() -> None:
    plan = _plan(
        [("shop", "11:20", "12:20"), ("food", "10:00", "11:00")],
    )
    profiles = _profiles(
        Amy=(["food"], [], 80),
        Ben=(["shopping"], [], 90),
    )

    report = check_plan(plan, profiles, PLACES, TRAVEL, CONFIG)

    assert report.feasible is True
    assert report.violations == []
    assert report.hard_limit_satisfaction == 1.0
    assert report.task_success is True
    assert report.per_friend_satisfaction == {"Amy": 1.0, "Ben": 1.0}
    assert report.fairness.min == 1.0
    assert report.fairness.gap == 0.0
    assert report.fairness.jain == 1.0


def test_unknown_place() -> None:
    report = check_plan(
        _plan([("missing", "10:00", "11:00")]),
        _profiles(Amy=(["food"], [], 100)),
        PLACES,
        TRAVEL,
        CONFIG,
    )

    assert _types(report) == ["unknown_place"]
    assert report.feasible is False
    assert report.task_success is False


def test_closed() -> None:
    report = check_plan(
        _plan([("food", "08:00", "09:00")]),
        _profiles(Amy=(["food"], [], 100)),
        PLACES,
        TRAVEL,
        CONFIG,
    )

    assert _types(report) == ["closed"]
    assert "outside 09:00-18:00" in report.violations[0].detail


def test_day_window_is_closed() -> None:
    early = _place("early", ["food"], "centre", opens="06:00", closes="12:00")
    report = check_plan(
        _plan([("early", "06:00", "07:00")]),
        _profiles(Amy=(["food"], [], 100)),
        [early],
        TRAVEL,
        CONFIG,
    )

    assert _types(report) == ["closed"]
    assert "outside day 07:00-23:00" in report.violations[0].detail


def test_too_short() -> None:
    report = check_plan(
        _plan([("food", "10:00", "10:30")]),
        _profiles(Amy=(["food"], [], 100)),
        PLACES,
        TRAVEL,
        CONFIG,
    )

    assert _types(report) == ["too_short"]
    assert report.violations[0].detail == "day 1 food is 30 min, needs 60"


def test_overlap() -> None:
    report = check_plan(
        _plan([("food", "10:00", "12:00"), ("shop", "11:00", "12:00")]),
        _profiles(Amy=(["food"], [], 100), Ben=(["shopping"], [], 100)),
        PLACES,
        TRAVEL,
        CONFIG,
    )

    assert _types(report) == ["overlap"]


def test_travel_gap() -> None:
    report = check_plan(
        _plan([("food", "10:00", "11:00"), ("shop", "11:10", "12:10")]),
        _profiles(Amy=(["food"], [], 100), Ben=(["shopping"], [], 100)),
        PLACES,
        TRAVEL,
        CONFIG,
    )

    assert _types(report) == ["travel_gap"]
    assert report.violations[0].detail == "day 1 food to shop gap 10 < 20"


def test_over_budget_flags_only_the_friends_who_cannot_pay() -> None:
    report = check_plan(
        _plan([("food", "10:00", "11:00")]),
        _profiles(Amy=(["food"], [], 15), Ben=(["food"], [], 20)),
        PLACES,
        TRAVEL,
        CONFIG,
    )

    assert _types(report) == ["over_budget"]
    assert report.violations[0].detail == "Amy cost 20 > budget 15"


def test_closed_and_too_short_are_both_listed() -> None:
    report = check_plan(
        _plan([("food", "08:00", "08:20")]),
        _profiles(Amy=(["food"], [], 100)),
        PLACES,
        TRAVEL,
        CONFIG,
    )

    assert _types(report) == ["closed", "too_short"]


def test_no_likes_score_one() -> None:
    report = check_plan(
        _plan([("food", "10:00", "11:00")]),
        _profiles(Amy=([], [], 100), Ben=(["food"], [], 100)),
        PLACES,
        TRAVEL,
        CONFIG,
    )

    assert report.per_friend_satisfaction == {"Amy": 1.0, "Ben": 1.0}
    assert report.task_success is True


def test_no_hard_limits_score_one_even_when_likes_are_missed() -> None:
    report = check_plan(
        _plan([("food", "10:00", "11:00")]),
        _profiles(Amy=(["hiking"], [], 100)),
        PLACES,
        TRAVEL,
        CONFIG,
    )

    assert report.feasible is True
    assert report.hard_limit_satisfaction == 1.0
    assert report.per_friend_satisfaction == {"Amy": 0.0}
    assert report.task_success is True


def test_all_zero_satisfaction_has_jain_index_one() -> None:
    report = check_plan(
        _plan([("food", "10:00", "11:00")]),
        _profiles(
            Amy=(["hiking"], [], 100),
            Ben=(["hiking"], [], 100),
            Cara=(["temples"], [], 100),
        ),
        PLACES,
        TRAVEL,
        CONFIG,
    )

    assert report.per_friend_satisfaction == {"Amy": 0.0, "Ben": 0.0, "Cara": 0.0}
    assert report.fairness.min == 0.0
    assert report.fairness.gap == 0.0
    assert report.fairness.jain == 1.0


def test_items_on_different_days_do_not_overlap_or_need_travel() -> None:
    report = check_plan(
        _plan(
            [("food", "10:00", "11:00")],
            [("shop", "10:00", "11:00")],
        ),
        _profiles(Amy=(["food"], [], 100), Ben=(["shopping"], [], 100)),
        PLACES,
        TRAVEL,
        {**CONFIG, "days": 2},
    )

    assert report.feasible is True
    assert report.violations == []
    assert report.per_friend_satisfaction == {"Amy": 1.0, "Ben": 1.0}


def test_exact_boundaries_are_legal() -> None:
    food = _place("food", ["food"], "centre", opens="10:00", closes="11:00", cost=20)
    shop = _place("shop", ["shopping"], "centre", opens="11:00", closes="12:00", cost=20)
    profiles = _profiles(
        Amy=(["food"], ["no_temples", "no_early_mornings"], 40),
        Ben=(["shopping"], [], 40),
    )

    report = check_plan(
        _plan([("food", "10:00", "11:00"), ("shop", "11:00", "12:00")]),
        profiles,
        [food, shop],
        TOUCH_TRAVEL,
        CONFIG,
    )

    assert report.violations == []
    assert report.feasible is True
    assert report.hard_limit_satisfaction == 1.0
    assert report.task_success is True

    cross = check_plan(
        _plan([("food", "10:00", "11:00"), ("shop", "11:20", "12:20")]),
        _profiles(Amy=(["food"], [], 50), Ben=(["shopping"], [], 50)),
        PLACES,
        TRAVEL,
        CONFIG,
    )
    assert cross.violations == []


def test_jain_index_for_scores_half_one_half() -> None:
    """Three friends score 0.5, 1.0, and 0.5.

    (0.5 + 1 + 0.5)^2 / (3 * (0.25 + 1 + 0.25)) = 4 / 4.5 = 8/9, about 0.89.
    """
    report = check_plan(
        _plan([("food", "10:00", "11:00"), ("shop", "11:20", "12:20")]),
        _profiles(
            Amy=(["food", "hiking"], [], 100),
            Ben=(["food"], [], 100),
            Cara=(["shopping", "temples"], [], 100),
        ),
        PLACES,
        TRAVEL,
        CONFIG,
    )

    assert report.per_friend_satisfaction == {"Amy": 0.5, "Ben": 1.0, "Cara": 0.5}
    assert report.fairness.min == 0.5
    assert report.fairness.gap == 0.5
    assert report.fairness.jain == pytest.approx(8 / 9)
    assert round(report.fairness.jain, 2) == 0.89
    assert report.task_success is True


def test_failed_hard_limit_blocks_task_success() -> None:
    report = check_plan(
        _plan([("temple", "10:00", "11:00")]),
        _profiles(
            Amy=(["temples"], ["no_temples"], 100),
            Ben=(["temples"], ["no_early_mornings"], 100),
        ),
        PLACES,
        TRAVEL,
        CONFIG,
    )

    assert report.feasible is True
    assert report.violations == []
    assert report.hard_limit_satisfaction == 0.5
    assert report.task_success is False


def test_unknown_hard_limit_is_rejected() -> None:
    with pytest.raises(ValueError, match="unknown hard limit"):
        check_plan(
            _plan([("food", "10:00", "11:00")]),
            _profiles(Amy=(["food"], ["no_flying"], 100)),
            PLACES,
            TRAVEL,
            CONFIG,
        )


@pytest.mark.parametrize("numbers", [[], [1], [1, 1], [1, 3], [1, 2, 3]])
def test_requested_days_must_appear_exactly_once(numbers: list[int]) -> None:
    plan = Plan(days=[PlanDay(day=n, items=[]) for n in numbers])
    report = check_plan(plan, {}, PLACES, TRAVEL, {**CONFIG, "days": 2})
    assert "invalid_days" in _types(report)
    assert not report.task_success


def test_two_distinct_activities_per_day_succeeds() -> None:
    plan = _plan(
        [("food", "10:00", "11:00"), ("shop", "11:20", "12:20")],
        [("temple", "10:00", "11:00"), ("hike", "11:05", "12:05")],
    )
    places = [FOOD, SHOP, TEMPLE, HIKE.model_copy(update={"closes": "13:00"})]
    report = check_plan(plan, {}, places, TRAVEL,
                        {**CONFIG, "days": 2, "min_activities_per_day": 2})
    assert report.task_success


@pytest.mark.parametrize("count", [0, 1])
def test_sparse_days_fail_by_default(count: int) -> None:
    plan = _plan([("food", "10:00", "11:00")] * count)
    config = {k: v for k, v in CONFIG.items() if k != "min_activities_per_day"}
    report = check_plan(plan, {}, PLACES, TRAVEL, config)
    assert "insufficient_activities" in _types(report)


@pytest.mark.parametrize("across_days", [False, True])
def test_repeated_places_fail(across_days: bool) -> None:
    visits = [("food", "10:00", "11:00"), ("food", "12:00", "13:00")]
    plan = _plan([visits[0]], [visits[1]]) if across_days else _plan(visits)
    report = check_plan(plan, {}, PLACES, TRAVEL,
                        {**CONFIG, "days": 2 if across_days else 1})
    assert _types(report) == ["repeated_place"]
