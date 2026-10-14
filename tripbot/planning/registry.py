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
    """Run setup A, B, or C. Only A is implemented.

    ``client`` replaces the Gemini client in tests. Callers that know the
    trip length should set ``config['days']`` before calling, because this
    signature has no separate days argument.
    """
    name = str(setup).upper()
    if name == "A":
        from tripbot.planning.setup_a import run_setup_a

        return run_setup_a(profiles, places, travel_times, config, client=client)
    raise ValueError(f"setup {setup} is not implemented")
