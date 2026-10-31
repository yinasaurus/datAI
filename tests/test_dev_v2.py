"""Development fixture coverage and witness validation, without API calls."""
from collections import Counter
from pathlib import Path

from scripts.generate_dev_v2 import build_dev_scenarios, satisfaction_witness
from scripts.validate_scenarios import find_feasible_plan, has_feasible_plan, validate_scenarios
from tripbot.config import load_config
from tripbot.schemas import Place, Profile, Scenario, TagCatalog, TravelTimes

ROOT = Path(__file__).resolve().parents[1]


def test_v2_is_development_only_and_has_positive_attainable_minimum():
    config = load_config(ROOT / "config.yaml", [])
    scenarios, mechanisms = build_dev_scenarios()
    assert len(scenarios) == 24
    assert {s.split for s in scenarios} == {"dev"}
    assert Counter(mechanisms.values()) == {"direct_recoverable": 12, "budget_pressure": 12}
    optima = set()
    for scenario in scenarios:
        row = satisfaction_witness(scenario, config)
        assert row["report"]["task_success"]
        assert row["minimum_satisfaction_lower_bound"] > 0
        assert row["optimum_proven"]
        optima.add(round(row["minimum_satisfaction_upper_bound"], 3))
    assert optima == {0.333, 0.5, 1.0}
    assert validate_scenarios(ROOT / "data" / "scenarios_v2" / "dev") == []


def test_budget_pairs_keep_preferences_and_restrictions_identical():
    scenarios, _ = build_dev_scenarios()
    for tight, loose in zip(scenarios[::2], scenarios[1::2]):
        assert tight.budget == "tight" and loose.budget == "loose"
        for name in tight.friends:
            assert tight.friends[name].likes == loose.friends[name].likes
            assert tight.friends[name].hard_limits == loose.friends[name].hard_limits
            assert tight.friends[name].budget < loose.friends[name].budget


def _toy():
    scenario = Scenario(id="toy", split="dev", days=2, n_friends=2, conflict="mild",
                        budget="tight", friends={
                            name: Profile(likes=["food"], hard_limits=[], budget=4)
                            for name in ("Amy", "Ben")})
    places = [Place(id=str(i), name=str(i), tags=["food"], cost=1, opens="10:00",
                    closes="12:00", area="a", duration_min=30, source="synthetic", verified=False)
              for i in range(4)]
    travel = TravelTimes(areas=["a"], minutes={}, same_area_minutes=0)
    catalog = TagCatalog(tags=["food"], hard_limits={})
    return scenario, places, travel, catalog


def test_feasibility_search_cannot_reuse_places_between_days():
    scenario, places, travel, catalog = _toy()
    assert not has_feasible_plan(scenario, places[:3], travel, catalog, "07:00", "23:00")
    witness = find_feasible_plan(scenario, places, travel, catalog, "07:00", "23:00")
    assert witness is not None
    assert [day.day for day in witness.days] == [1, 2]
    assert all(len(day.items) >= 2 for day in witness.days)
    assert len({item.place_id for day in witness.days for item in day.items}) == 4
    assert not has_feasible_plan(scenario, places, travel, catalog, "07:00", "23:00", 3)


def test_feasibility_search_obeys_time_and_whole_trip_budget():
    scenario, places, travel, catalog = _toy()
    places = [p.model_copy(update={"closes": "10:45"}) for p in places]
    assert not has_feasible_plan(scenario, places, travel, catalog, "07:00", "23:00")
    scenario, places, travel, catalog = _toy()
    scenario.friends["Ben"].budget = 3
    assert not has_feasible_plan(scenario, places, travel, catalog, "07:00", "23:00")
