"""Setup C: one agent per friend, negotiation rounds, then a mediator.

Round 0 is one proposal each, with no exchange. Each later round shows every
agent the others' latest plans. The mediator merges the final proposals, and
the checker then revises that merge the same way setup B does.
"""

from __future__ import annotations

import json
from typing import Any

from pydantic import ValidationError

from tripbot.llm import LLMResult, call_llm
from tripbot.planning.prompts import (
    FRIEND_SYSTEM,
    MEDIATOR_SYSTEM,
    PLAN_RESPONSE_SCHEMA,
    friend_prompt,
    mediator_prompt,
    negotiation_prompt,
    revision_prompt,
)
from tripbot.planning.registry import PlanResult
from tripbot.planning.setup_a import parse_plan_text
from tripbot.planning.setup_b import _check_reply
from tripbot.schemas import Place, Profile, TravelTimes


def proposal_calls(n_friends: int, negotiation_rounds: int) -> int:
    """Model calls before checker repairs: one per friend per round, plus the mediator.

    Round 0 is included. ``negotiation_rounds`` counts only the later exchanges.
    Each repair after the merge adds one more call, up to ``max_revisions``.
    """
    rounds = 1 + max(0, negotiation_rounds)
    return n_friends * rounds + 1


def run_setup_c(
    profiles: dict[str, Profile],
    places: list[Place],
    travel_times: TravelTimes,
    config: dict[str, Any],
    *,
    client: Any = None,
) -> PlanResult:
    """Negotiate per friend, merge, then revise the merge while it has violations."""
    negotiation_rounds = max(0, int(config["negotiation_rounds"]))
    max_revisions = max(0, int(config["max_revisions"]))
    tokens_in = 0
    tokens_out = 0
    seconds = 0.0
    trace: list[dict[str, Any]] = []
    proposals: dict[str, str] = {}

    for round_index in range(negotiation_rounds + 1):
        previous = dict(proposals)
        for name, profile in profiles.items():
            if round_index == 0:
                prompt = friend_prompt(name, profile, places, travel_times, config)
                system = FRIEND_SYSTEM
            else:
                others = {other: text for other, text in previous.items() if other != name}
                prompt = negotiation_prompt(
                    name,
                    profile,
                    places,
                    travel_times,
                    config,
                    others,
                    previous.get(name, ""),
                )
                system = FRIEND_SYSTEM
            result = _generate(system, prompt, config, client)
            tokens_in, tokens_out, seconds = _add(tokens_in, tokens_out, seconds, result)
            proposals[name] = result.text
            _record(
                trace,
                step="friend",
                result=result,
                friend=name,
                round=round_index,
                parsed=_parsed(result.text),
            )

    base = mediator_prompt(profiles, proposals, places, travel_times, config)
    result = _generate(MEDIATOR_SYSTEM, base, config, client)
    tokens_in, tokens_out, seconds = _add(tokens_in, tokens_out, seconds, result)
    plan, violations = _check_reply(result.text, profiles, places, travel_times, config)
    _record(trace, step="mediator", result=result, violations=violations)
    previous_text = result.text

    for revision in range(max_revisions):
        if plan is not None and not violations:
            break
        prompt = revision_prompt(base, previous_text, violations)
        result = _generate(MEDIATOR_SYSTEM, prompt, config, client)
        tokens_in, tokens_out, seconds = _add(tokens_in, tokens_out, seconds, result)
        plan, violations = _check_reply(result.text, profiles, places, travel_times, config)
        _record(trace, step="revision", result=result, violations=violations)
        previous_text = result.text

    return PlanResult(
        plan=plan,
        attempts=len(trace),
        llm_calls=len(trace),
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        seconds=seconds,
        trace=trace,
    )


def _generate(
    system: str,
    prompt: str,
    config: dict[str, Any],
    client: Any,
) -> LLMResult:
    return call_llm(
        system,
        prompt,
        config,
        json_mode=True,
        client=client,
        response_schema=PLAN_RESPONSE_SCHEMA,
    )


def _add(tokens_in: int, tokens_out: int, seconds: float, result: LLMResult) -> tuple[int, int, float]:
    return tokens_in + result.tokens_in, tokens_out + result.tokens_out, seconds + result.seconds


def _record(trace: list[dict[str, Any]], *, step: str, result: LLMResult, **extra: Any) -> None:
    trace.append(
        {
            "step": step,
            "attempt": len(trace) + 1,
            "tokens_in": result.tokens_in,
            "tokens_out": result.tokens_out,
            "seconds": result.seconds,
            "cached": result.cached,
            **extra,
        }
    )


def _parsed(text: str) -> bool:
    try:
        parse_plan_text(text)
    except (json.JSONDecodeError, ValidationError, ValueError):
        return False
    return True
