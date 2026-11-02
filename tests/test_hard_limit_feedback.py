"""Targeted repair diagnostics stay separate from metric definitions."""
from pathlib import Path

import pytest

from tripbot.checker.check_plan import check_plan
from tripbot.checker.rules import hard_limit_failures
from tripbot.schemas import Plan, Profile, load_places, load_tag_catalog, load_travel_times

ROOT = Path(__file__).resolve().parents[1]


def feedback(days, limits):
    plan = Plan.model_validate({"days": days})
    places = load_places(ROOT / "data/places.json")
    profiles = {name: Profile(likes=[], hard_limits=names, budget=100) for name, names in limits.items()}
    catalog = load_tag_catalog(ROOT / "data/tags.json")
    return hard_limit_failures(plan, profiles, {p.id: p for p in places}, catalog)


def day(number, identifier, start="10:00", end="11:00"):
    return {"day": number, "items": [{"place_id": identifier, "start": start, "end": end}]}


def test_forbidden_tag_names_owner_day_place_and_rule_without_place_prose():
    rows = feedback([day(2, "p12")], {"Ben": ["no_temples"]})
    assert rows == [{"type": "hard_limit", "detail":
                    "Ben: no_temples; forbids tag temples; offending visits: day 2 p12 has forbidden tag temples"}]


def test_all_offending_visits_are_listed_in_one_row_per_failed_rule():
    rows = feedback([day(2, "p12"), day(1, "p11")], {"Ben": ["no_temples"], "Cara": ["no_temples"]})
    assert len(rows) == 2
    assert rows[0]["detail"].startswith("Ben:") and rows[1]["detail"].startswith("Cara:")
    assert rows[0]["detail"].index("day 1 p11") < rows[0]["detail"].index("day 2 p12")


def test_start_rule_names_actual_and_required_times_and_keeps_boundary_legal():
    rows = feedback([day(1, "p01", "09:30", "10:30"), day(2, "p14")],
                    {"Amy": ["no_early_mornings"]})
    assert len(rows) == 1
    assert "earliest allowed start 10:00" in rows[0]["detail"]
    assert "day 1 p01 starts 09:30" in rows[0]["detail"]
    assert "day 2" not in rows[0]["detail"]


def test_unknown_places_remain_separate_but_start_limits_still_apply():
    rows = feedback([day(1, "unknown", "09:00", "10:00")],
                    {"Amy": ["no_temples", "no_early_mornings"]})
    assert len(rows) == 1 and "unknown starts 09:00" in rows[0]["detail"]


def test_satisfied_limits_produce_no_feedback():
    assert feedback([day(1, "p01")], {"Amy": ["no_temples", "no_early_mornings"]}) == []


def test_unknown_rule_is_not_silently_accepted():
    with pytest.raises(ValueError, match="unknown hard limit"):
        feedback([day(1, "p01")], {"Amy": ["unknown_rule"]})


def test_richer_feedback_does_not_move_hard_limits_into_feasibility():
    plan = Plan.model_validate({"days": [day(1, "p12")]})
    profiles = {"Ben": Profile(likes=["temples"], hard_limits=["no_temples"], budget=100)}
    places = load_places(ROOT / "data/places.json")
    report = check_plan(plan, profiles, places, load_travel_times(ROOT / "data/travel_times.json"),
                        {"days": 1, "min_activities_per_day": 1, "day_start": "07:00", "day_end": "23:00",
                         "paths": {"tags": str(ROOT / "data/tags.json")}})
    assert report.feasible and report.violations == []
    assert report.hard_limit_satisfaction == 0 and not report.task_success
