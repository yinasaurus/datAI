"""Dispatch a planning setup and return one PlanResult."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from tripbot.schemas import Place, Plan, Profile, TravelTimes


@dataclass
class PlanResult:
    """The outcome of one planning run, including a failed parse."""

    plan: Plan | None
    attempts: int
    llm_calls: int
    tokens_in: int
    tokens_out: int
    seconds: float
    trace: list[dict[str, Any]] = field(default_factory=list)


def make_plan(
    setup: str,
    profiles: dict[str, Profile],
    places: list[Place],
    travel_times: TravelTimes,
    config: dict[str, Any],
    *,
    client: Any = None,
) -> PlanResult:
    """Run setup A, B, or C.

    ``client`` replaces the Gemini client in tests. Callers that know the
    trip length should set ``config['days']`` before calling, because this
    signature has no separate days argument.
    """
    name = str(setup).upper()
    if name not in {"A", "B", "C"}:
        raise ValueError(f"setup {setup} is not implemented")
    from tripbot.planning.eligibility import eligible_place_ids

    ids, filtering = eligible_place_ids(profiles, places, config)
    planner_config = dict(config)
    planner_config["_eligible_place_ids"] = ids
    if name == "A":
        from tripbot.planning.setup_a import run_setup_a
        result = run_setup_a(profiles, places, travel_times, planner_config, client=client)
    elif name == "B":
        from tripbot.planning.setup_b import run_setup_b
        result = run_setup_b(profiles, places, travel_times, planner_config, client=client)
    else:
        from tripbot.planning.setup_c import run_setup_c
        result = run_setup_c(profiles, places, travel_times, planner_config, client=client)
    if result.trace:
        result.trace[0]["place_filter"] = filtering
    return result
