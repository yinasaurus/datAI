"""Setup A: one model call sees every friend and returns one plan."""

from __future__ import annotations

import json
from typing import Any

from pydantic import ValidationError

from tripbot.llm import call_llm
from tripbot.planning.prompts import PLAN_RESPONSE_SCHEMA, SYSTEM_PROMPT, setup_a_prompt
from tripbot.planning.registry import PlanResult
from tripbot.schemas import Place, Plan, Profile, TravelTimes


def run_setup_a(
    profiles: dict[str, Profile],
    places: list[Place],
    travel_times: TravelTimes,
    config: dict[str, Any],
    *,
    client: Any = None,
) -> PlanResult:
    """Ask the model once. Invalid JSON or a bad plan becomes a failed result."""
    prompt = setup_a_prompt(profiles, places, travel_times, config)
    result = call_llm(
        SYSTEM_PROMPT,
        prompt,
        config,
        json_mode=True,
        client=client,
        response_schema=PLAN_RESPONSE_SCHEMA,
    )
    try:
        plan = parse_plan_text(result.text)
    except (json.JSONDecodeError, ValidationError, ValueError) as exc:
        return PlanResult(
            plan=None,
            attempts=1,
            llm_calls=1,
            tokens_in=result.tokens_in,
            tokens_out=result.tokens_out,
            seconds=result.seconds,
            trace=[{"step": "setup_a", "error": str(exc), "text": result.text[:500]}],
        )
    return PlanResult(
        plan=plan,
        attempts=1,
        llm_calls=1,
        tokens_in=result.tokens_in,
        tokens_out=result.tokens_out,
        seconds=result.seconds,
        trace=[{"step": "setup_a", "cached": result.cached}],
    )


def parse_plan_text(text: str) -> Plan:
    """Parse model text into a Plan. Raises if the JSON or the schema is invalid."""
    return Plan.model_validate(json.loads(_strip_fence(text)))


def _strip_fence(text: str) -> str:
    body = text.strip()
    if not body.startswith("```"):
        return body
    lines = body.splitlines()
    if lines and lines[0].startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip().startswith("```"):
        lines = lines[:-1]
    return "\n".join(lines).strip()
