"""Setup B: one planner, then the checker, then up to max_revisions fixes."""

from __future__ import annotations

import json
from typing import Any

from pydantic import ValidationError

from tripbot.checker.check_plan import check_plan
from tripbot.llm import call_llm
from tripbot.planning.prompts import (
    PLAN_RESPONSE_SCHEMA,
    SYSTEM_PROMPT,
    revision_prompt,
    setup_a_prompt,
    with_prompt_version,
)
from tripbot.planning.registry import PlanResult
from tripbot.planning.setup_a import parse_plan_text
from tripbot.schemas import Place, Plan, Profile, TravelTimes


def run_setup_b(
    profiles: dict[str, Profile],
    places: list[Place],
    travel_times: TravelTimes,
    config: dict[str, Any],
    *,
    client: Any = None,
) -> PlanResult:
    """Plan once, then revise while the checker reports violations.

    ``max_revisions`` of 0 keeps the first plan and does not call the model
    again, which is the same plan setup A would return.
    """
    base = setup_a_prompt(profiles, places, travel_times, config)
    prompt = base
    max_revisions = max(0, int(config["max_revisions"]))
    tokens_in = 0
    tokens_out = 0
    seconds = 0.0
    trace: list[dict[str, Any]] = []
    plan: Plan | None = None

    for revision in range(max_revisions + 1):
        result = call_llm(
            SYSTEM_PROMPT,
            prompt,
            config,
            json_mode=True,
            client=client,
            response_schema=PLAN_RESPONSE_SCHEMA,
        )
        tokens_in += result.tokens_in
        tokens_out += result.tokens_out
        seconds += result.seconds
        plan, violations = _check_reply(
            result.text,
            profiles,
            places,
            travel_times,
            config,
        )
        trace.append(
            with_prompt_version(
                {
                    "step": "setup_b" if revision == 0 else "revision",
                    "attempt": revision + 1,
                    "tokens_in": result.tokens_in,
                    "tokens_out": result.tokens_out,
                    "seconds": result.seconds,
                    "cached": result.cached,
                    "violations": violations,
                }
            )
        )
        if plan is not None and not violations:
            break
        if revision >= max_revisions:
            break
        prompt = revision_prompt(base, result.text, violations)

    return PlanResult(
        plan=plan,
        attempts=len(trace),
        llm_calls=len(trace),
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        seconds=seconds,
        trace=trace,
    )


def _check_reply(
    text: str,
    profiles: dict[str, Profile],
    places: list[Place],
    travel_times: TravelTimes,
    config: dict[str, Any],
) -> tuple[Plan | None, list[dict[str, str]]]:
    try:
        plan = parse_plan_text(text)
    except (json.JSONDecodeError, ValidationError, ValueError) as exc:
        return None, [{"type": "invalid_plan", "detail": str(exc)}]
    report = check_plan(plan, profiles, places, travel_times, config)
    violations = [{"type": item.type, "detail": item.detail} for item in report.violations]
    return plan, violations
