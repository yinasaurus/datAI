"""Feasibility, hard-limit, and fairness rules for a plan.

These functions do not call a model. A visit that overlaps the previous one is
reported as ``overlap``. A positive gap that is still too short for travel is
``travel_gap``. A negative gap is not also a travel gap, so the two types stay
separate when failures are counted.
"""

from __future__ import annotations

from typing import Any

from tripbot.schemas import (
    Fairness,
    Place,
    Plan,
    PlanDay,
    PlanItem,
    Profile,
    TagCatalog,
    TravelTimes,
    Violation,
    parse_hhmm,
    travel_minutes,
)


def feasibility_violations(
    plan: Plan,
    profiles: dict[str, Profile],
    places_by_id: dict[str, Place],
    travel_times: TravelTimes,
    config: dict[str, Any],
) -> list[Violation]:
    """Return every feasibility failure, in the order the spec lists them."""
    violations: list[Violation] = []
    violations.extend(_unknown_places(plan, places_by_id))
    violations.extend(_closed(plan, places_by_id, config))
    violations.extend(_too_short(plan, places_by_id))
    violations.extend(_overlaps(plan))
    violations.extend(_travel_gaps(plan, places_by_id, travel_times))
    violations.extend(_over_budget(plan, profiles, places_by_id))
    violations.extend(_trip_structure(plan, config))
    return violations


def _trip_structure(plan: Plan, config: dict[str, Any]) -> list[Violation]:
    """Require the requested days, sufficient activities, and unique visits."""
    expected = list(range(1, int(config.get("days", 1)) + 1))
    actual = sorted(day.day for day in plan.days)
    found: list[Violation] = []
    if actual != expected:
        found.append(Violation(type="invalid_days", detail=f"expected days {expected}, got {actual}"))
    minimum = int(config.get("min_activities_per_day", 2))
    seen: set[str] = set()
    for day in _days(plan):
        if len(day.items) < minimum:
            found.append(Violation(
                type="insufficient_activities",
                detail=f"day {day.day} has {len(day.items)} activities, needs {minimum}",
            ))
        for item in day.items:
            if item.place_id in seen:
                found.append(Violation(type="repeated_place", detail=f"day {day.day} {item.place_id}"))
            seen.add(item.place_id)
    return found


def hard_limit_failures(
    plan: Plan,
    profiles: dict[str, Profile],
    places_by_id: dict[str, Place],
    catalog: TagCatalog,
) -> list[dict[str, str]]:
    """Describe failed hard limits for repairs, separately from feasibility."""
    tags = _tags_in_plan(plan, places_by_id)
    starts = [_start(item) for day in _days(plan) for item in day.items]
    return [
        {"type": "hard_limit", "detail": f"{name}: {limit_name}"}
        for name, profile in profiles.items()
        for limit_name in profile.hard_limits
        if not _limit_holds(limit_name, catalog, tags, starts)
    ]


def hard_limit_satisfaction(
    plan: Plan,
    profiles: dict[str, Profile],
    places_by_id: dict[str, Place],
    catalog: TagCatalog,
) -> float:
    """Return satisfied hard limits divided by the total across all friends.

    No hard limits scores 1.0. Budget is not a hard limit. ``forbid_tag`` fails
    when any known place carries that tag. ``earliest_start`` fails when any
    item starts earlier than the limit.
    """
    tags_in_plan = _tags_in_plan(plan, places_by_id)
    starts = [_start(item) for day in _days(plan) for item in day.items]
    satisfied = 0
    total = 0
    for profile in profiles.values():
        for limit_name in profile.hard_limits:
            total += 1
            if _limit_holds(limit_name, catalog, tags_in_plan, starts):
                satisfied += 1
    if total == 0 or satisfied == total:
        return 1.0
    return satisfied / total


def per_friend_satisfaction(
    plan: Plan,
    profiles: dict[str, Profile],
    places_by_id: dict[str, Place],
) -> dict[str, float]:
    """Return the share of each friend's liked tags that the plan covers.

    A friend with no likes scores 1.0. A tag counts once it appears on any
    known place in the plan.
    """
    tags_in_plan = _tags_in_plan(plan, places_by_id)
    scores: dict[str, float] = {}
    for name, profile in profiles.items():
        if not profile.likes:
            scores[name] = 1.0
            continue
        covered = sum(1 for tag in profile.likes if tag in tags_in_plan)
        scores[name] = 1.0 if covered == len(profile.likes) else covered / len(profile.likes)
    return scores


def fairness(scores: dict[str, float]) -> Fairness:
    """Return min, max-minus-min, and Jain's index for the satisfaction scores.

    Jain's index is ``(sum s)^2 / (n * sum s^2)``. Equal scores, including all
    zeros, score 1.0.
    """
    values = list(scores.values())
    if not values:
        return Fairness(min=1.0, gap=0.0, jain=1.0)
    low = min(values)
    high = max(values)
    return Fairness(min=low, gap=high - low, jain=jain_index(values))


def jain_index(scores: list[float]) -> float:
    """Return Jain's fairness index. Equal scores, including all zeros, are 1."""
    if not scores:
        return 1.0
    total = sum(scores)
    squares = sum(score * score for score in scores)
    if squares == 0:
        return 1.0
    return (total * total) / (len(scores) * squares)


def _unknown_places(plan: Plan, places_by_id: dict[str, Place]) -> list[Violation]:
    found: list[Violation] = []
    for day in _days(plan):
        for item in day.items:
            if item.place_id not in places_by_id:
                found.append(Violation(type="unknown_place", detail=f"day {day.day} {item.place_id}"))
    return found


def _closed(plan: Plan, places_by_id: dict[str, Place], config: dict[str, Any]) -> list[Violation]:
    day_start = parse_hhmm(str(config["day_start"]))
    day_end = parse_hhmm(str(config["day_end"]))
    found: list[Violation] = []
    for day in _days(plan):
        for item in day.items:
            place = places_by_id.get(item.place_id)
            if place is None:
                continue
            start = _start(item)
            end = _end(item)
            if start < day_start or end > day_end:
                found.append(
                    Violation(
                        type="closed",
                        detail=(
                            f"day {day.day} {item.place_id} outside day "
                            f"{config['day_start']}-{config['day_end']}"
                        ),
                    )
                )
            if start < parse_hhmm(place.opens) or end > parse_hhmm(place.closes):
                found.append(
                    Violation(
                        type="closed",
                        detail=f"day {day.day} {item.place_id} outside {place.opens}-{place.closes}",
                    )
                )
    return found


def _too_short(plan: Plan, places_by_id: dict[str, Place]) -> list[Violation]:
    found: list[Violation] = []
    for day in _days(plan):
        for item in day.items:
            place = places_by_id.get(item.place_id)
            if place is None:
                continue
            length = _end(item) - _start(item)
            if length < place.duration_min:
                found.append(
                    Violation(
                        type="too_short",
                        detail=f"day {day.day} {item.place_id} is {length} min, needs {place.duration_min}",
                    )
                )
    return found


def _overlaps(plan: Plan) -> list[Violation]:
    found: list[Violation] = []
    for day in _days(plan):
        ordered = sorted(day.items, key=lambda item: (_start(item), item.place_id))
        for index, earlier in enumerate(ordered):
            for later in ordered[index + 1 :]:
                if _start(later) < _end(earlier):
                    found.append(
                        Violation(
                            type="overlap",
                            detail=f"day {day.day} {earlier.place_id} and {later.place_id}",
                        )
                    )
    return found


def _travel_gaps(
    plan: Plan,
    places_by_id: dict[str, Place],
    travel_times: TravelTimes,
) -> list[Violation]:
    found: list[Violation] = []
    for day in _days(plan):
        ordered = sorted(day.items, key=lambda item: (_start(item), item.place_id))
        for earlier, later in zip(ordered, ordered[1:]):
            gap = _start(later) - _end(earlier)
            if gap < 0:
                continue
            previous = places_by_id.get(earlier.place_id)
            nxt = places_by_id.get(later.place_id)
            if previous is None or nxt is None:
                continue
            needed = travel_minutes(travel_times, previous.area, nxt.area)
            if gap < needed:
                found.append(
                    Violation(
                        type="travel_gap",
                        detail=(
                            f"day {day.day} {earlier.place_id} to {later.place_id} "
                            f"gap {gap} < {needed}"
                        ),
                    )
                )
    return found


def _over_budget(
    plan: Plan,
    profiles: dict[str, Profile],
    places_by_id: dict[str, Place],
) -> list[Violation]:
    total = 0
    for day in _days(plan):
        for item in day.items:
            place = places_by_id.get(item.place_id)
            if place is not None:
                total += place.cost
    found: list[Violation] = []
    for name, profile in profiles.items():
        if total > profile.budget:
            found.append(
                Violation(type="over_budget", detail=f"{name} cost {total} > budget {profile.budget}")
            )
    return found


def _limit_holds(
    limit_name: str,
    catalog: TagCatalog,
    tags_in_plan: set[str],
    starts: list[int],
) -> bool:
    try:
        rule = catalog.hard_limits[limit_name]
    except KeyError:
        raise ValueError(f"unknown hard limit {limit_name}") from None
    if rule.type == "forbid_tag":
        return rule.tag not in tags_in_plan
    if rule.time is None:
        raise ValueError(f"{limit_name} has no time")
    earliest = parse_hhmm(rule.time)
    return all(start >= earliest for start in starts)


def _tags_in_plan(plan: Plan, places_by_id: dict[str, Place]) -> set[str]:
    tags: set[str] = set()
    for day in _days(plan):
        for item in day.items:
            place = places_by_id.get(item.place_id)
            if place is not None:
                tags.update(place.tags)
    return tags


def _days(plan: Plan) -> list[PlanDay]:
    return sorted(plan.days, key=lambda day: day.day)


def _start(item: PlanItem) -> int:
    return parse_hhmm(item.start)


def _end(item: PlanItem) -> int:
    return parse_hhmm(item.end)
