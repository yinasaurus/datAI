"""Repair arithmetic suggests edits without applying or certifying them."""
from pathlib import Path

from tripbot.planning.prompts import repair_budget_summary
from tripbot.planning.repair_options import cost_compatible_options
from tripbot.schemas import Plan, Profile, load_places

ROOT = Path(__file__).resolve().parents[1]


def inputs():
    places = load_places(ROOT / "data/places.json")
    profiles = {"Amy": Profile(likes=["food"], hard_limits=[], budget=23),
                "Ben": Profile(likes=["shopping"], hard_limits=["no_temples"], budget=24)}
    config = {"days": 2, "min_activities_per_day": 2, "day_start": "07:00", "day_end": "23:00",
              "paths": {"tags": str(ROOT / "data/tags.json")}}
    return profiles, places, config


def plan(ids):
    return Plan.model_validate({"days": [{"day": number, "items": [
        {"place_id": identifier, "start": "10:00", "end": "11:00"} for identifier in names]}
        for number, names in enumerate(ids, 1)]})


def test_replacement_recalculates_entire_trip_without_selecting_a_plan():
    profiles, places, config = inputs()
    previous = plan([["p01", "p14"], ["p16", "p19"]])  # 26 total.
    original = previous.model_dump()
    options = cost_compatible_options(previous, profiles, places, config)
    replace = next(o for o in options["replacements"] if o["replace_place_id"] == "p19")
    museum = next(o for o in replace["candidates"] if o["place_id"] == "p07")
    assert museum == {"place_id": "p07", "cost": 6, "resulting_whole_trip_cost": 23}
    used = {"p01", "p14", "p16", "p19"}
    for edit in options["replacements"]:
        for candidate in edit["candidates"]:
            assert candidate["place_id"] not in used
            assert candidate["place_id"] not in {"p12", "p11"}  # Forbidden, even if cheap/free.
            assert candidate["resulting_whole_trip_cost"] <= 23
    assert previous.model_dump() == original
    assert "not complete or scheduled repairs" in options["scope"]


def test_addition_uses_remaining_whole_trip_budget_and_missing_day():
    profiles, places, config = inputs()
    previous = plan([["p01", "p14"], ["p16"]])  # 17 total; six remain.
    options = cost_compatible_options(previous, profiles, places, config)
    assert options["replacements"] == []
    assert len(options["additions"]) == 1
    addition = options["additions"][0]
    assert addition["day"] == 2 and addition["activities_missing"] == 1
    assert {"place_id": "p07", "cost": 6, "resulting_whole_trip_cost": 23} in addition["candidates"]
    assert all(c["cost"] <= 6 for c in addition["candidates"])


def test_missing_entire_day_is_explicit_and_options_cannot_be_blindly_combined():
    profiles, places, config = inputs()
    options = cost_compatible_options(plan([["p01", "p14"]]), profiles, places, config)
    assert options["additions"][0]["day"] == 2
    assert options["additions"][0]["activities_missing"] == 2
    assert "Do not combine options" in options["caution"]


def test_no_single_edit_option_does_not_claim_infeasibility():
    profiles, places, config = inputs()
    options = cost_compatible_options(plan([["p01", "p16"], ["p19"]]), profiles, places, config)
    assert options["additions"][0]["candidates"] == []  # Total22; no unused eligible place costs <=1.
    assert "do not prove infeasibility" in options["no_options_note"]


def test_unknown_ids_never_produce_invented_cost_suggestions():
    profiles, places, config = inputs()
    options = cost_compatible_options(plan([["unknown"]]), profiles, places, config)
    assert options["replacements"] == options["additions"] == []
    assert "unknown" in options["unavailable_reason"]
    summary = repair_budget_summary(plan([["unknown"]]).model_dump_json(), profiles, places, config=config)
    assert summary["previous_total_cost_per_person"] is None
    assert "cost_compatible_options" not in summary


def test_supplied_eligibility_cannot_be_expanded_by_repair_helper():
    profiles, places, config = inputs()
    config["_eligible_place_ids"] = ["p07"]
    options = cost_compatible_options(plan([["p01", "p14"], ["p16"]]), profiles, places, config)
    assert [c["place_id"] for c in options["additions"][0]["candidates"]] == ["p07"]


def test_cost_only_options_do_not_claim_a_valid_time_slot():
    profiles, places, config = inputs()
    # An option can have a three-hour duration; no actual insertion time is supplied.
    places = [p.model_copy(update={"duration_min": 180}) if p.id == "p07" else p for p in places]
    options = cost_compatible_options(plan([["p01", "p14"], ["p16"]]), profiles, places, config)
    museum = next(c for c in options["additions"][0]["candidates"] if c["place_id"] == "p07")
    assert "start" not in museum and "end" not in museum
    assert "Recheck all constraints" in options["caution"]
