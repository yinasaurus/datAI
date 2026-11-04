"""Shared candidate filtering; the complete dataset remains the scoring authority."""
from __future__ import annotations

from typing import Any

from tripbot.schemas import Place, Profile, load_tag_catalog, parse_hhmm


def eligible_place_ids(
    profiles: dict[str, Profile], places: list[Place], config: dict[str, Any],
) -> tuple[list[str], dict[str, Any]]:
    """Exclude forbidden categories and places with no allowed visit window.

    No budget/preferences/ranking or reference answers influence eligibility.
    A surviving place still needs a legal scheduled time, checked after planning.
    """
    catalog = load_tag_catalog(config["paths"]["tags"])
    forbidden: set[str] = set()
    earliest = parse_hhmm(str(config["day_start"]))
    end = parse_hhmm(str(config["day_end"]))
    for profile in profiles.values():
        for name in profile.hard_limits:
            if name not in catalog.hard_limits:
                raise ValueError(f"unknown hard limit {name}")
            rule = catalog.hard_limits[name]
            if rule.type == "forbid_tag" and rule.tag is not None:
                forbidden.add(rule.tag)
            elif rule.time is not None:
                earliest = max(earliest, parse_hhmm(rule.time))
    allowed = []
    excluded = []
    for place in places:
        reasons = [f"forbidden_tag:{tag}" for tag in sorted(forbidden & set(place.tags))]
        if max(earliest, parse_hhmm(place.opens)) + place.duration_min > min(end, parse_hhmm(place.closes)):
            reasons.append("no_allowed_visit_window")
        if reasons:
            excluded.append({"place_id": place.id, "reasons": reasons})
        else:
            allowed.append(place.id)
    return allowed, {"version": 1, "input_place_count": len(places),
                     "eligible_place_ids": allowed, "excluded": excluded}


def prompt_places(places: list[Place], config: dict[str, Any]) -> list[Place]:
    """Restrict prompt rows to the shared list computed at the make_plan boundary."""
    ids = config.get("_eligible_place_ids")
    if ids is None:
        return places
    allowed = set(ids)
    return [place for place in places if place.id in allowed]
