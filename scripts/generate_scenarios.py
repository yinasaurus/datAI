"""Write balanced dev and held-out scenarios from a fixed seed.

Mild means one clash: two friends cannot both be fully satisfied.
Strong means two such clashes. A clash is a liked tag that another friend
rules out, either by forbidding that tag or by an earliest start that no
place for the tag can meet. Hard limits and budgets stay solvable because a
plan can skip the blocked tags.

Do not run this again after data/scenarios/heldout is frozen. Pass
``--overwrite`` only when you intend to replace files.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tripbot.config import load_config
from tripbot.schemas import Place, Profile, Scenario, TagCatalog, parse_hhmm, place_fits

# Placeholder per-person totals for the whole trip, in the same units as place
# costs. Replace both ends before treating budget as a real study factor.
# With the placeholder places, two days of the cheapest allowed visit cost 20,
# so every friend budget must stay at or above 20 or the scenario is unsolvable.
BUDGET_RANGES: dict[str, tuple[int, int]] = {
    "tight": (60, 90),
    "loose": (200, 280),
}

TRIP_DAYS = 2
FRIEND_NAMES = ["Amy", "Ben", "Cara", "Dan", "Eve"]
SAFE_TAGS = ["food", "shopping", "culture", "outdoor", "markets"]
N_FRIENDS = (2, 3, 5)
CONFLICTS = ("mild", "strong")
BUDGET_LEVELS = ("loose", "tight")
CELLS = [
    (n_friends, conflict, budget_level)
    for n_friends in N_FRIENDS
    for conflict in CONFLICTS
    for budget_level in BUDGET_LEVELS
]
DEV_COPIES = 1
HELDOUT_COPIES = 2


def build_scenarios(seed: int) -> list[Scenario]:
    """Build 12 dev scenarios and 24 held-out scenarios, one seed stream."""
    rng = random.Random(seed)
    scenarios: list[Scenario] = []
    for split, copies, first_id in (("dev", DEV_COPIES, 1), ("heldout", HELDOUT_COPIES, 101)):
        index = 0
        for copy in range(copies):
            for n_friends, conflict, budget_level in CELLS:
                low, high = BUDGET_RANGES[budget_level]
                budgets = [rng.randint(low, high) for _ in range(n_friends)]
                scenario_id = f"s_{first_id + index:03d}"
                index += 1
                scenarios.append(
                    Scenario(
                        id=scenario_id,
                        split=split,
                        days=TRIP_DAYS,
                        n_friends=n_friends,
                        conflict=conflict,
                        budget=budget_level,
                        friends=_friends(n_friends, conflict, budgets, copy),
                    )
                )
    return scenarios


def preference_conflicts(
    scenario: Scenario,
    places: list[Place],
    catalog: TagCatalog,
    day_start: str,
    day_end: str,
) -> list[tuple[str, str, str]]:
    """Return ``(friend, other, tag)`` clashes that block joint full satisfaction.

    Full satisfaction means every liked tag appears on at least one place and
    every hard limit holds. One row here means that combination is impossible.
    """
    found: list[tuple[str, str, str]] = []
    for name, profile in scenario.friends.items():
        for other_name, other in scenario.friends.items():
            if name == other_name:
                continue
            for tag in profile.likes:
                if _ruled_out(tag, other, places, catalog, day_start, day_end):
                    found.append((name, other_name, tag))
    return found


def write_scenarios(
    root: Path,
    scenarios: list[Scenario],
    *,
    overwrite: bool = False,
) -> tuple[list[Path], list[Path]]:
    """Write scenario JSON. Existing files are kept unless ``overwrite`` is set."""
    written: list[Path] = []
    skipped: list[Path] = []
    for scenario in scenarios:
        path = root / "data" / "scenarios" / scenario.split / f"{scenario.id}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists() and not overwrite:
            skipped.append(path)
            continue
        text = json.dumps(scenario.model_dump(), indent=2) + "\n"
        path.write_text(text, encoding="utf-8")
        written.append(path)
    return written, skipped


def _friends(
    n_friends: int,
    conflict: str,
    budgets: list[int],
    tag_shift: int,
) -> dict[str, Profile]:
    names = FRIEND_NAMES[:n_friends]
    safe = [SAFE_TAGS[(index + tag_shift) % len(SAFE_TAGS)] for index in range(n_friends)]
    profiles = {
        name: Profile(likes=[safe[index]], hard_limits=[], budget=budgets[index])
        for index, name in enumerate(names)
    }
    profiles[names[0]] = Profile(likes=["temples"], hard_limits=[], budget=budgets[0])
    profiles[names[1]] = Profile(
        likes=[safe[1]],
        hard_limits=["no_temples"],
        budget=budgets[1],
    )
    if conflict == "strong" and n_friends == 2:
        profiles[names[0]] = Profile(
            likes=["temples", "hiking"],
            hard_limits=[],
            budget=budgets[0],
        )
        profiles[names[1]] = Profile(
            likes=[safe[1]],
            hard_limits=["no_temples", "no_early_mornings"],
            budget=budgets[1],
        )
    elif conflict == "strong":
        profiles[names[1]] = Profile(
            likes=["nightlife"],
            hard_limits=["no_temples"],
            budget=budgets[1],
        )
        profiles[names[2]] = Profile(
            likes=[safe[2]],
            hard_limits=["no_nightlife"],
            budget=budgets[2],
        )
    return profiles


def _ruled_out(
    tag: str,
    other: Profile,
    places: list[Place],
    catalog: TagCatalog,
    day_start: str,
    day_end: str,
) -> bool:
    if _forbids(other, tag, catalog):
        return True
    earliest = _earliest(other, catalog)
    if earliest is None:
        return False
    bound = _later(day_start, earliest)
    return not any(tag in place.tags and place_fits(place, bound, day_end) for place in places)


def _forbids(profile: Profile, tag: str, catalog: TagCatalog) -> bool:
    for name in profile.hard_limits:
        rule = catalog.hard_limits[name]
        if rule.type == "forbid_tag" and rule.tag == tag:
            return True
    return False


def _earliest(profile: Profile, catalog: TagCatalog) -> str | None:
    times = [
        catalog.hard_limits[name].time
        for name in profile.hard_limits
        if catalog.hard_limits[name].type == "earliest_start"
        and catalog.hard_limits[name].time is not None
    ]
    if not times:
        return None
    return max(times, key=parse_hhmm)


def _later(left: str, right: str) -> str:
    return left if parse_hhmm(left) >= parse_hhmm(right) else right


def main(argv: list[str] | None = None) -> int:
    """Write scenario files under data/scenarios using the config seed."""
    config = load_config(ROOT / "config.yaml", [])
    parser = argparse.ArgumentParser(description="Generate balanced scenario files")
    parser.add_argument("--seed", type=int, default=int(config["seed"]))
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="replace scenario files that already exist",
    )
    args = parser.parse_args(argv)
    scenarios = build_scenarios(args.seed)
    written, skipped = write_scenarios(ROOT, scenarios, overwrite=args.overwrite)
    print(f"wrote {len(written)} scenarios, left {len(skipped)} in place, seed {args.seed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
