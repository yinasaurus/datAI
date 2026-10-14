"""Tests for scenario generation and the hard-limit search."""

import json
from collections import Counter
from pathlib import Path

from scripts.generate_scenarios import (
    BUDGET_RANGES,
    build_scenarios,
    preference_conflicts,
    write_scenarios,
)
from scripts.validate_scenarios import has_feasible_plan, main, validate_scenarios
from tripbot.config import load_config
from tripbot.schemas import (
    Place,
    Profile,
    Scenario,
    TagCatalog,
    TravelTimes,
    load_places,
    load_scenario,
    load_tag_catalog,
    load_travel_times,
)

ROOT = Path(__file__).resolve().parents[1]


def _inputs() -> tuple[list[Place], TravelTimes, TagCatalog, str, str]:
    config = load_config(ROOT / "config.yaml", [])
    return (
        load_places(ROOT / "data" / "places.json"),
        load_travel_times(ROOT / "data" / "travel_times.json"),
        load_tag_catalog(ROOT / "data" / "tags.json"),
        str(config["day_start"]),
        str(config["day_end"]),
    )


def test_generation_is_balanced_and_stable() -> None:
    config = load_config(ROOT / "config.yaml", [])
    first = build_scenarios(int(config["seed"]))
    second = build_scenarios(int(config["seed"]))

    assert [item.model_dump() for item in first] == [item.model_dump() for item in second]
    dev = [item for item in first if item.split == "dev"]
    heldout = [item for item in first if item.split == "heldout"]
    assert len(dev) == 12
    assert len(heldout) == 24
    assert Counter((item.n_friends, item.conflict, item.budget) for item in dev) == {
        (n_friends, conflict, level): 1
        for n_friends in (2, 3, 5)
        for conflict in ("mild", "strong")
        for level in ("loose", "tight")
    }
    assert Counter((item.n_friends, item.conflict, item.budget) for item in heldout) == {
        (n_friends, conflict, level): 2
        for n_friends in (2, 3, 5)
        for conflict in ("mild", "strong")
        for level in ("loose", "tight")
    }


def test_every_generated_scenario_conflicts_but_stays_solvable() -> None:
    places, travel, catalog, day_start, day_end = _inputs()

    for scenario in build_scenarios(42):
        clashes = preference_conflicts(scenario, places, catalog, day_start, day_end)
        expected = 1 if scenario.conflict == "mild" else 2
        assert len(clashes) == expected
        involved = {name for name, _, _ in clashes} | {name for _, name, _ in clashes}
        assert len(involved) >= 2
        low, high = BUDGET_RANGES[scenario.budget]
        assert all(low <= profile.budget <= high for profile in scenario.friends.values())
        assert has_feasible_plan(scenario, places, travel, catalog, day_start, day_end)


def test_shipped_files_match_the_generator() -> None:
    config = load_config(ROOT / "config.yaml", [])
    for scenario in build_scenarios(int(config["seed"])):
        path = ROOT / "data" / "scenarios" / scenario.split / f"{scenario.id}.json"
        assert load_scenario(path) == scenario


def test_validator_reports_an_unsolvable_scenario(tmp_path: Path) -> None:
    scenario = Scenario(
        id="s_900",
        split="dev",
        days=2,
        n_friends=2,
        conflict="mild",
        budget="tight",
        friends={
            "Amy": Profile(likes=["food"], hard_limits=[], budget=1),
            "Ben": Profile(likes=["shopping"], hard_limits=["no_temples"], budget=1),
        },
    )
    folder = tmp_path / "dev"
    folder.mkdir()
    path = folder / "s_900.json"
    path.write_text(json.dumps(scenario.model_dump()), encoding="utf-8")

    problems = validate_scenarios(folder)

    assert problems == ["s_900: unsolvable for hard limits and budgets"]


def test_validator_reports_an_unknown_like(tmp_path: Path) -> None:
    scenario = Scenario(
        id="s_901",
        split="dev",
        days=1,
        n_friends=2,
        conflict="mild",
        budget="loose",
        friends={
            "Amy": Profile(likes=["spa"], hard_limits=[], budget=100),
            "Ben": Profile(likes=["food"], hard_limits=[], budget=100),
        },
    )
    folder = tmp_path / "dev"
    folder.mkdir()
    (folder / "s_901.json").write_text(json.dumps(scenario.model_dump()), encoding="utf-8")

    problems = validate_scenarios(folder)

    assert any("unknown tag spa" in problem for problem in problems)


def test_write_scenarios_does_not_overwrite_unless_asked(tmp_path: Path) -> None:
    scenarios = build_scenarios(42)[:1]
    written, skipped = write_scenarios(tmp_path, scenarios)
    assert len(written) == 1
    assert skipped == []
    written_again, skipped_again = write_scenarios(tmp_path, scenarios)
    assert written_again == []
    assert len(skipped_again) == 1
    replaced, _ = write_scenarios(tmp_path, scenarios, overwrite=True)
    assert len(replaced) == 1


def test_shipped_scenarios_pass_the_validator() -> None:
    assert validate_scenarios(ROOT / "data" / "scenarios") == []
    assert main([]) == 0
