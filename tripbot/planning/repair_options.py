"""Arithmetic-only repair options, without selecting or scheduling a new plan."""
from __future__ import annotations

from typing import Any

from tripbot.planning.eligibility import eligible_place_ids
from tripbot.schemas import Place, Plan, Profile


def cost_compatible_options(
    plan: Plan, profiles: dict[str, Profile], places: list[Place], config: dict[str, Any],
) -> dict[str, Any]:
    """List single-edit options; timing/travel and combined edits are not validated."""
    result: dict[str, Any] = {
        "scope": "Single-edit cost-compatible candidates only; not complete or scheduled repairs.",
        "caution": "Recheck all constraints. Do not combine options without recalculating total cost.",
        "replacements": [], "additions": [],
    }
    costs = {place.id: place.cost for place in places}
    visits = [(day.day, index, item.place_id) for day in plan.days
              for index, item in enumerate(day.items, start=1)]
    unknown = sorted({identifier for _, _, identifier in visits} - costs.keys())
    if unknown:
        return {**result, "unavailable_reason": "Total cost is unknown because the plan contains unknown IDs."}
    total = sum(costs[identifier] for _, _, identifier in visits)
    limit = min((profile.budget for profile in profiles.values()), default=0)
    eligible, _ = eligible_place_ids(profiles, places, config)
    allowed = set(eligible)
    if "_eligible_place_ids" in config:
        allowed &= set(config["_eligible_place_ids"])
    used = {identifier for _, _, identifier in visits}
    unused = sorted((place for place in places if place.id in allowed - used),
                    key=lambda place: (place.cost, place.id))
    if total > limit:
        for day, index, identifier in visits:
            options = [{"place_id": place.id, "cost": place.cost,
                        "resulting_whole_trip_cost": total - costs[identifier] + place.cost}
                       for place in unused if total - costs[identifier] + place.cost <= limit]
            result["replacements"].append({"day": day, "item_number": index,
                "replace_place_id": identifier, "current_visit_cost": costs[identifier],
                "candidates": options})
    minimum = int(config.get("min_activities_per_day", 2))
    for day in range(1, int(config.get("days", 1)) + 1):
        count = sum(len(entry.items) for entry in plan.days if entry.day == day)
        if count < minimum:
            options = [{"place_id": place.id, "cost": place.cost,
                        "resulting_whole_trip_cost": total + place.cost}
                       for place in unused if total + place.cost <= limit]
            result["additions"].append({"day": day, "activities_missing": minimum - count,
                                        "candidates": options})
    result["no_options_note"] = (
        "Empty candidate lists do not prove infeasibility; several coordinated edits may be needed. "
        "Place IDs must remain unique across the entire itinerary."
    )
    return result
