"""Create a fictional development benchmark with exhaustively audited budget choices."""
from __future__ import annotations

import argparse
import json
from itertools import combinations
from pathlib import Path
from typing import Any

import yaml

from tripbot.checker.check_plan import check_plan
from tripbot.config import load_config
from tripbot.schemas import Place, Plan, PlanDay, PlanItem, Profile, Scenario, TagCatalog, TravelTimes

ROOT = Path(__file__).resolve().parents[1]
NAMES = ["Amy", "Ben", "Cara", "Dan", "Eve"]


def build_world(n: int) -> tuple[list[Place], TagCatalog, TravelTimes]:
    """Each private visit covers two unique likes; a shared visit covers one each."""
    tags = [f"interest_{i}_{part}" for i in range(n) for part in ("a", "b")] + ["neutral"]
    def place(identifier: str, likes: list[str], cost: int) -> Place:
        return Place(id=identifier, name=f"FICTIONAL {identifier}", tags=likes, cost=cost,
                     opens="10:00", closes="18:00", duration_min=60, area="synthetic_centre",
                     source="synthetic: designed benchmark fixture; no real venue", verified=False)
    places = [place(f"private_{i}", [f"interest_{i}_a", f"interest_{i}_b"], 6) for i in range(n)]
    places.append(place("shared", [f"interest_{i}_a" for i in range(n)], 3))
    places.extend(place(f"neutral_{i}", ["neutral"], 0) for i in range(4))
    return places, TagCatalog(tags=tags, hard_limits={}), TravelTimes(
        areas=["synthetic_centre"], minutes={}, same_area_minutes=5)


def build_scenarios(n: int) -> list[Scenario]:
    """Return constrained budgets and an unconstrained full-satisfaction control."""
    caps = sorted({6 * max(1, n // 2), 6 * (n - 1), 6 * n})
    scenarios = []
    for cap in caps:
        # Rotate the first named role between group sizes; no person is inherently excluded.
        order = NAMES[:n][1:] + NAMES[:n][:1]
        friends = {name: Profile(likes=[f"interest_{i}_a", f"interest_{i}_b"],
                                 hard_limits=[], budget=cap) for i, name in enumerate(order)}
        scenarios.append(Scenario(
            id=f"syn_n{n}_budget{cap:02d}", split="dev", days=2, n_friends=n,
            conflict="strong" if cap < 6 * (n - 1) else "mild",
            budget="loose" if cap == 6 * n else "tight", friends=friends))
    return scenarios


def schedule_subset(places: tuple[Place, ...]) -> Plan:
    """Canonical schedule; any 4–10 distinct visits fit in these identical windows."""
    if not 4 <= len(places) <= 10:
        raise ValueError("synthetic subset must have 4 to 10 places")
    split = len(places) // 2
    days = []
    for number, chunk in enumerate((places[:split], places[split:]), 1):
        items = []
        for index, place in enumerate(chunk):
            start = 600 + index * 65
            end = start + 60
            items.append(PlanItem(place_id=place.id, start=f"{start // 60:02d}:{start % 60:02d}",
                                  end=f"{end // 60:02d}:{end % 60:02d}"))
        days.append(PlanDay(day=number, items=items))
    return Plan(days=days)


def audit_scenario(scenario: Scenario, places: list[Place], config: dict[str, Any]) -> dict[str, Any]:
    """Enumerate every visit subset; timing/order cannot change preference coverage."""
    cap = min(profile.budget for profile in scenario.friends.values())
    vectors = set()
    examples = []
    for count in range(4, len(places) + 1):
        for subset in combinations(places, count):
            cost = sum(p.cost for p in subset)
            if cost > cap:
                continue
            plan = schedule_subset(subset)
            report = check_plan(plan, scenario.friends, places, TravelTimes(
                areas=["synthetic_centre"], minutes={}, same_area_minutes=5), config)
            if not report.task_success:
                raise ValueError(f"canonical synthetic schedule failed: {report}")
            scores = tuple(report.per_friend_satisfaction.values())
            vectors.add(scores)
            examples.append((report.fairness.min, sum(scores) / len(scores), -cost,
                             plan, report))
    if not examples:
        raise ValueError("synthetic scenario has no feasible itinerary")
    best = max(examples, key=lambda row: row[:3])
    individual = {}
    for name, profile in scenario.friends.items():
        witness = next(row for row in examples if row[4].per_friend_satisfaction[name] == 1)
        individual[name] = {"plan": witness[3].model_dump(), "report": witness[4].model_dump()}
    # Every b-tag occurs only on its owner's private visit, costing six units.
    full_cost = 6 * scenario.n_friends
    if cap < full_cost and len(vectors) < 2:
        raise ValueError("constrained scenario must offer distinct satisfaction outcomes")
    return {
        "scenario_id": scenario.id, "budget_cap_per_person": cap,
        "all_friends_full_satisfaction_minimum_cost": full_cost,
        "all_friends_full_satisfaction_feasible": cap >= full_cost,
        "individual_full_satisfaction_witnesses": individual,
        "distinct_satisfaction_vectors": len(vectors),
        "feasible_visit_subsets": len(examples),
        "optimal_minimum_satisfaction": best[0],
        "optimal_mean_subject_to_maximum_minimum": best[1],
        "optimal_plan": best[3].model_dump(), "optimal_report": best[4].model_dump(),
        "zero_minimum_alternative": next((
            {"plan": row[3].model_dump(), "report": row[4].model_dump()}
            for row in examples if row[0] == 0 and row[1] == best[1]), None),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "data" / "synthetic_v1")
    args = parser.parse_args()
    destination = args.output.resolve()
    if destination.exists():
        parser.error("output already exists; choose a fresh folder")
    base = load_config(ROOT / "config.yaml", [])
    files: dict[Path, str] = {}
    summary = []
    for n in (2, 3, 5):
        folder = destination / f"n{n}"
        places, catalog, travel = build_world(n)
        config = {**base, "days": 2, "min_activities_per_day": 2, "day_start": "10:00", "day_end": "18:00",
                  "paths": {**base["paths"], "places": str(folder / "places.json"),
                            "tags": str(folder / "tags.json"), "travel_times": str(folder / "travel_times.json"),
                            "llm_log": str(ROOT / "logs" / "synthetic_llm_calls.jsonl"),
                            "results": str(ROOT / "results" / "synthetic_runs.jsonl")}}
        # Absolute paths are written relative to the repo when possible for portability.
        for key, value in config["paths"].items():
            try:
                config["paths"][key] = str(Path(value).relative_to(ROOT))
            except ValueError:
                pass
        files[folder / "places.json"] = json.dumps([p.model_dump() for p in places], indent=2) + "\n"
        files[folder / "tags.json"] = catalog.model_dump_json(indent=2) + "\n"
        files[folder / "travel_times.json"] = travel.model_dump_json(indent=2) + "\n"
        files[folder / "config.yaml"] = yaml.safe_dump(config, sort_keys=False)
        scenarios = build_scenarios(n)
        for scenario in scenarios:
            files[folder / "dev" / f"{scenario.id}.json"] = scenario.model_dump_json(indent=2) + "\n"
    # Write staging data only inside the fresh output; audits need the catalogue files.
    for path, content in files.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
    for n in (2, 3, 5):
        folder = destination / f"n{n}"
        config = load_config(folder / "config.yaml", [])
        places, _, _ = build_world(n)
        for scenario in build_scenarios(n):
            row = audit_scenario(scenario, places, config)
            summary.append(row)
            print(f"{scenario.id}: min={row['optimal_minimum_satisfaction']:.2f}, "
                  f"mean={row['optimal_mean_subject_to_maximum_minimum']:.2f}, "
                  f"distinct outcomes={row['distinct_satisfaction_vectors']}")
    (destination / "development_audit.json").write_text(json.dumps(summary, indent=2) + "\n")
    (destination / "manifest.json").write_text(json.dumps({
        "version": "synthetic-v1-development-draft", "fictional": True, "heldout_created": False,
        "currency": "abstract budget units, not SGD", "mechanism": "budget competition",
        "group_sizes": [2, 3, 5], "scenarios": len(summary),
        "note": "hand-designed controls, not independent samples of human travel behaviour",
    }, indent=2) + "\n")


if __name__ == "__main__":
    main()
