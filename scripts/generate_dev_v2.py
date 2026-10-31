"""Build development-only v2 fixtures and checker-verified satisfaction witnesses.

No model requests, held-out generation, or main experiment evaluation happen here.
"""
from __future__ import annotations

import argparse
import json
from itertools import permutations
from pathlib import Path

from tripbot.checker.check_plan import check_plan
from tripbot.config import load_config
from tripbot.schemas import (
    Plan, PlanDay, PlanItem, Profile, Scenario, load_places, load_tag_catalog,
    load_travel_times, parse_hhmm, travel_minutes,
)

ROOT = Path(__file__).resolve().parents[1]


def build_dev_scenarios() -> tuple[list[Scenario], dict[str, str]]:
    """Create matched budget conditions with rotating restriction owners."""
    scenarios = []
    mechanisms = {}
    names = ["Amy", "Ben", "Cara", "Dan", "Eve"]
    for mechanism in ("direct_recoverable", "budget_pressure"):
        for n in (2, 3, 5):
            for severity in ("mild", "strong"):
                # Identical profiles across budget pairs isolate the budget change.
                offset = (n + (severity == "strong")) % n
                order = names[:n][offset:] + names[:n][:offset]
                for level in ("tight", "loose"):
                    limit = (23 if level == "tight" else 120) if mechanism == "direct_recoverable" else (7 if level == "tight" else 30)
                    likes = [["food", "culture"], ["shopping", "culture"],
                             ["outdoor", "culture"], ["nightlife", "culture"], ["hiking", "culture"]]
                    friends = {name: Profile(likes=likes[i], hard_limits=[], budget=limit + i)
                               for i, name in enumerate(order)}
                    if mechanism == "direct_recoverable":
                        friends[order[0]].likes = ["temples", "food"]
                        friends[order[1]].hard_limits = ["no_temples"]
                        # Keep every person's likes at least partly attainable.
                        for profile in friends.values():
                            if "hiking" in profile.likes:
                                profile.likes = ["outdoor", "culture"]
                        if severity == "strong":
                            friends[order[0]].hard_limits = ["no_nightlife"]
                            friends[order[1]].likes = ["nightlife", "culture"]
                    elif severity == "strong":
                        friends[order[0]].likes = ["shopping", "nightlife", "culture"]
                        friends[order[1]].likes = ["hiking", "food", "culture"]
                        friends[order[-1]].hard_limits = ["no_early_mornings"]
                    identifier = f"v2_dev_{len(scenarios) + 1:03d}"
                    scenarios.append(Scenario(id=identifier, split="dev", days=2, n_friends=n,
                                              conflict=severity, budget=level, friends=friends))
                    mechanisms[identifier] = mechanism
    return scenarios, mechanisms


def satisfaction_witness(scenario: Scenario, config: dict) -> dict:
    """Search four-visit plans; distinguish an attained upper bound from a lower bound.

    Every returned plan is checked by the production checker. The independent
    upper bound removes globally forbidden/unaffordable/unvisitable tags but
    ignores joint scheduling and total combination cost, so it is optimistic.
    """
    places = load_places(ROOT / config["paths"]["places"])
    catalog = load_tag_catalog(ROOT / config["paths"]["tags"])
    travel = load_travel_times(ROOT / config["paths"]["travel_times"])
    budget = min(p.budget for p in scenario.friends.values())
    forbidden = {catalog.hard_limits[l].tag for p in scenario.friends.values()
                 for l in p.hard_limits if catalog.hard_limits[l].type == "forbid_tag"}
    earliest = max([parse_hhmm(config["day_start"])] + [parse_hhmm(catalog.hard_limits[l].time)
                   for p in scenario.friends.values() for l in p.hard_limits
                   if catalog.hard_limits[l].type == "earliest_start"])
    end_limit = parse_hhmm(config["day_end"])
    candidates = [p for p in places if forbidden.isdisjoint(p.tags) and p.cost <= budget
                  and max(earliest, parse_hhmm(p.opens)) + p.duration_min <= min(end_limit, parse_hhmm(p.closes))]
    def score(tags):
        return min(len(set(p.likes) & tags) / len(p.likes) if p.likes else 1.0
                   for p in scenario.friends.values())
    upper = score({tag for p in candidates for tag in p.tags})
    pairs = []
    def clock(n):
        return f"{n // 60:02d}:{n % 60:02d}"
    for a, b in permutations(candidates, 2):
        start_a = max(earliest, parse_hhmm(a.opens))
        end_a = start_a + a.duration_min
        start_b = max(earliest, parse_hhmm(b.opens), end_a + travel_minutes(travel, a.area, b.area))
        end_b = start_b + b.duration_min
        if end_b > min(end_limit, parse_hhmm(b.closes)) or a.cost + b.cost > budget:
            continue
        pairs.append((a.cost + b.cost, {a.id, b.id}, set(a.tags + b.tags), [
            PlanItem(place_id=a.id, start=clock(start_a), end=clock(end_a)),
            PlanItem(place_id=b.id, start=clock(start_b), end=clock(end_b)),
        ]))
    pairs.sort(key=lambda pair: pair[0])
    best = None
    best_score = -1.0
    for a in pairs:
        for b in pairs:
            if a[0] + b[0] > budget:
                break
            if not a[1].isdisjoint(b[1]):
                continue
            value = score(a[2] | b[2])
            if value > best_score:
                best_score = value
                best = Plan(days=[PlanDay(day=1, items=a[3]), PlanDay(day=2, items=b[3])])
            if best_score == upper:
                break
        if best_score == upper:
            break
    if best is None:
        raise ValueError(f"{scenario.id}: no four-visit witness; broader feasibility is not disproved")
    report = check_plan(best, scenario.friends, places, travel, {**config, "days": scenario.days})
    if not report.task_success:
        raise ValueError(f"{scenario.id}: witness rejected by checker: {report}")
    return {"scenario_id": scenario.id, "minimum_satisfaction_lower_bound": best_score,
            "minimum_satisfaction_upper_bound": upper, "optimum_proven": best_score == upper,
            "plan": best.model_dump(), "report": report.model_dump()}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "data" / "scenarios_v2")
    args = parser.parse_args()
    config = load_config(ROOT / "config.yaml", [])
    if int(config.get("min_activities_per_day", 2)) != 2:
        parser.error("the development witness audit currently requires two activities per day")
    scenarios, mechanisms = build_dev_scenarios()
    # Finish all validation before writing any fixtures.
    audit = [satisfaction_witness(s, config) for s in scenarios]
    paths = [args.output / "dev" / f"{s.id}.json" for s in scenarios]
    paths += [args.output / "manifest.json", args.output / "development_audit.json"]
    if any(p.exists() for p in paths):
        parser.error("output already exists; use a fresh --output folder to preserve prior versions")
    for scenario, path in zip(scenarios, paths):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(scenario.model_dump_json(indent=2) + "\n")
    manifest = {"version": "v2-development-draft", "heldout_created": False,
                "mechanisms": mechanisms, "status": "review before freezing",
                "severity_definition": {
                    "direct_recoverable": "mild: one direct forbidden preference; strong: two; each has an unblocked alternative",
                    "budget_pressure": "mild: two likes each; strong: first two roles have three likes and one role forbids early mornings; proposed severity, not empirically ranked",
                }}
    paths[-2].write_text(json.dumps(manifest, indent=2) + "\n")
    paths[-1].write_text(json.dumps(audit, indent=2) + "\n")
    for row in audit:
        print(f"{row['scenario_id']}: min satisfaction {row['minimum_satisfaction_lower_bound']:.3f} to "
              f"{row['minimum_satisfaction_upper_bound']:.3f}; proven={row['optimum_proven']}")


if __name__ == "__main__":
    main()
