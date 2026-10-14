"""Assemble a check report from the feasibility and satisfaction rules."""

from __future__ import annotations

from typing import Any

from tripbot.checker.rules import (
    fairness,
    feasibility_violations,
    hard_limit_satisfaction,
    per_friend_satisfaction,
)
from tripbot.schemas import Place, Plan, Profile, Report, TravelTimes, load_tag_catalog


def check_plan(
    plan: Plan,
    profiles: dict[str, Profile],
    places: list[Place],
    travel_times: TravelTimes,
    config: dict[str, Any],
) -> Report:
    """Check a plan in code and return a report. This does not call a model.

    ``feasible`` is false when any feasibility violation is present.
    ``task_success`` also requires every hard limit to be satisfied. Liked tags
    affect satisfaction and fairness only.
    """
    catalog = load_tag_catalog(config["paths"]["tags"])
    places_by_id = {place.id: place for place in places}
    violations = feasibility_violations(plan, profiles, places_by_id, travel_times, config)
    hard_limits = hard_limit_satisfaction(plan, profiles, places_by_id, catalog)
    scores = per_friend_satisfaction(plan, profiles, places_by_id)
    feasible = not violations
    return Report(
        feasible=feasible,
        violations=violations,
        hard_limit_satisfaction=hard_limits,
        per_friend_satisfaction=scores,
        fairness=fairness(scores),
        task_success=feasible and hard_limits == 1.0,
    )
