"""Check scenario files and search for one plan that meets hard limits and budgets."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pydantic import ValidationError

from tripbot.config import load_config
from tripbot.schemas import (
    Place,
    Scenario,
    TagCatalog,
    TravelTimes,
    load_places,
    load_tag_catalog,
    load_travel_times,
    parse_hhmm,
    travel_minutes,
)

MAX_VISITS_PER_DAY = 3


def validate_scenarios(scenarios_dir: Path, root: Path | None = None) -> list[str]:
    """Return problems for every scenario JSON under ``scenarios_dir``.

    Schema and vocabulary errors are listed first. A scenario is unsolvable
    when the search finds no plan that obeys every hard limit and every budget.
    """
    repo = ROOT if root is None else root
    config = load_config(repo / "config.yaml", [])
    try:
        catalog = load_tag_catalog(repo / config["paths"]["tags"])
        places = load_places(repo / config["paths"]["places"])
        travel = load_travel_times(repo / config["paths"]["travel_times"])
    except (OSError, json.JSONDecodeError, ValidationError, ValueError) as exc:
        return [f"data: {exc}"]

    problems: list[str] = []
    files = _scenario_files(scenarios_dir)
    if not files:
        return [f"no scenario files in {scenarios_dir}"]
    for path in files:
        problems.extend(
            _check_file(
                path,
                places,
                travel,
                catalog,
                day_start=str(config["day_start"]),
                day_end=str(config["day_end"]),
            )
        )
    return problems


def has_feasible_plan(
    scenario: Scenario,
    places: list[Place],
    travel: TravelTimes,
    catalog: TagCatalog,
    day_start: str,
    day_end: str,
) -> bool:
    """Search for a plan with at least one visit each day, inside limits and budgets.

    Candidates that carry a forbidden tag are removed first. The clock then
    tries cheaper places first and stops at the first schedule that fits.
    Likes are not part of this search.
    """
    earliest = parse_hhmm(day_start)
    end_limit = parse_hhmm(day_end)
    forbidden: set[str] = set()
    for profile in scenario.friends.values():
        for limit_name in profile.hard_limits:
            rule = catalog.hard_limits[limit_name]
            if rule.type == "forbid_tag" and rule.tag is not None:
                forbidden.add(rule.tag)
            elif rule.type == "earliest_start" and rule.time is not None:
                earliest = max(earliest, parse_hhmm(rule.time))
    budget = min(profile.budget for profile in scenario.friends.values())
    candidates = sorted(
        (place for place in places if forbidden.isdisjoint(place.tags)),
        key=lambda place: (place.cost, place.id),
    )

    def visit_end(place: Place, cursor: int, previous: str | None) -> int | None:
        start = max(parse_hhmm(place.opens), earliest)
        if previous is not None:
            start = max(start, cursor + travel_minutes(travel, previous, place.area))
        end = start + place.duration_min
        if end > parse_hhmm(place.closes) or end > end_limit:
            return None
        return end

    def days_from(day_index: int, spent: int) -> bool:
        if day_index == scenario.days:
            return True
        return fill_day(day_index, spent, earliest, None, frozenset())

    def fill_day(
        day_index: int,
        spent: int,
        cursor: int,
        previous: str | None,
        used: frozenset[str],
    ) -> bool:
        if used and days_from(day_index + 1, spent):
            return True
        if len(used) >= MAX_VISITS_PER_DAY:
            return False
        for place in candidates:
            if place.id in used or spent + place.cost > budget:
                continue
            end = visit_end(place, cursor, previous)
            if end is None:
                continue
            if fill_day(day_index, spent + place.cost, end, place.area, used | {place.id}):
                return True
        return False

    return days_from(0, 0)


def _check_file(
    path: Path,
    places: list[Place],
    travel: TravelTimes,
    catalog: TagCatalog,
    *,
    day_start: str,
    day_end: str,
) -> list[str]:
    try:
        scenario = Scenario.model_validate(json.loads(path.read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError, ValidationError, ValueError) as exc:
        return [f"{path.name}: {exc}"]

    problems: list[str] = []
    if path.parent.name != scenario.split:
        problems.append(f"{scenario.id}: split {scenario.split} is not folder {path.parent.name}")
    if path.stem != scenario.id:
        problems.append(f"{scenario.id}: file name is {path.name}")
    for friend, profile in scenario.friends.items():
        for tag in profile.likes:
            if tag not in catalog.tags:
                problems.append(f"{scenario.id}: {friend} likes unknown tag {tag}")
        for limit_name in profile.hard_limits:
            if limit_name not in catalog.hard_limits:
                problems.append(f"{scenario.id}: {friend} has unknown hard limit {limit_name}")
    if problems:
        return problems
    if not has_feasible_plan(scenario, places, travel, catalog, day_start, day_end):
        problems.append(f"{scenario.id}: unsolvable for hard limits and budgets")
    return problems


def _scenario_files(scenarios_dir: Path) -> list[Path]:
    if scenarios_dir.is_file():
        return [scenarios_dir]
    return sorted(scenarios_dir.rglob("*.json"))


def main(argv: list[str] | None = None) -> int:
    """Print each problem and return 1 when any scenario fails."""
    parser = argparse.ArgumentParser(description="Validate scenario JSON files")
    parser.add_argument(
        "--scenarios",
        type=Path,
        default=ROOT / "data" / "scenarios",
    )
    args = parser.parse_args(argv)
    problems = validate_scenarios(args.scenarios)
    if problems:
        for problem in problems:
            print(problem)
        print(f"unsolvable or invalid: {len(problems)}")
        return 1
    count = len(_scenario_files(args.scenarios))
    print(f"checked {count} scenarios, unsolvable: 0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
