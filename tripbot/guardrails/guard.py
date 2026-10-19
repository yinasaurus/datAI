"""Decide whether one bot or agent action may proceed.

``guard(action, context)`` gets ``{"type": ..., "payload": ...}`` from
``tripbot.bot.guard_adapter.check_action``. The payloads are:

- ``reply``: ``{"text": str}``. Blocked if it holds the canary token or
  repeats an untrusted place description, or if ``context["plan"]`` costs more
  than ``budget_cap``.
- ``book``: ``{"plan": dict, "confirmed": bool}``. Allowed only when
  ``confirmed`` is true, the triggering message is a human ``/confirm``, and the
  plan costs no more than ``budget_cap``.
- ``tool_call``: ``{"name": str, "arguments": dict}``. Only ``search_places``,
  ``check_plan`` and ``mock_book`` are allowed. An agent can never confirm a
  booking or change protected settings such as ``budget_cap``.

Chat text and place descriptions are untrusted data. The budget cap comes only
from ``context["config"]``, which agents never write.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from tripbot.guardrails.canary import contains_canary, load_canary
from tripbot.schemas import load_places

ALLOWED_TOOLS = frozenset({"search_places", "check_plan", "mock_book"})
PROTECTED_KEYS = frozenset({"budget_cap", "guardrails", "canary", "canary_token", "config"})
CONFIRM_COMMAND = "/confirm"
MIN_ECHO_LENGTH = 20


@dataclass(frozen=True)
class GuardResult:
    """Whether an action may proceed, and a short reason."""

    allowed: bool
    reason: str


def guard(action: Mapping[str, Any], context: Mapping[str, Any]) -> GuardResult:
    """Check one action against the guardrail rules. Unknown actions are blocked."""
    kind = action.get("type")
    payload = action.get("payload")
    if not isinstance(payload, Mapping):
        return GuardResult(False, f"{kind} payload is not a mapping")
    if kind == "reply":
        return _check_reply(payload, context)
    if kind == "book":
        return _check_book(payload, context)
    if kind == "tool_call":
        return _check_tool_call(payload)
    return GuardResult(False, f"unknown action type {kind!r}")


def plan_cost(plan: Any, places_path: str) -> int:
    """Return the cost per person of a plan dict. Unknown place ids cost 0."""
    costs = _place_costs(str(places_path))
    body = plan.model_dump() if hasattr(plan, "model_dump") else plan
    total = 0
    for day in (body or {}).get("days", []):
        for item in day.get("items", []):
            total += costs.get(str(item.get("place_id")), 0)
    return total


def _check_reply(payload: Mapping[str, Any], context: Mapping[str, Any]) -> GuardResult:
    text = payload.get("text")
    if not isinstance(text, str):
        return GuardResult(False, "reply text is not a string")
    canary = str(context.get("canary") or load_canary())
    if contains_canary(text, canary):
        return GuardResult(False, "canary token in reply")
    if _echoes_untrusted(text, context.get("place_descriptions") or []):
        return GuardResult(False, "reply repeats untrusted place text")
    plan = context.get("plan")
    if plan is not None:
        over = _over_cap(plan, context)
        if over is not None:
            return over
    return GuardResult(True, "reply is clean")


def _check_book(payload: Mapping[str, Any], context: Mapping[str, Any]) -> GuardResult:
    if payload.get("confirmed") is not True:
        return GuardResult(False, "booking needs confirmed=true")
    if not _is_confirm_command(context.get("chat_text")):
        return GuardResult(False, "booking needs a human /confirm command")
    plan = payload.get("plan")
    if not isinstance(plan, Mapping) or not plan.get("days"):
        return GuardResult(False, "booking has no plan")
    over = _over_cap(plan, context)
    if over is not None:
        return over
    return GuardResult(True, "human confirmed booking")


def _check_tool_call(payload: Mapping[str, Any]) -> GuardResult:
    name = payload.get("name")
    if name not in ALLOWED_TOOLS:
        return GuardResult(False, f"tool {name!r} is not allowed")
    arguments = payload.get("arguments") or {}
    if not isinstance(arguments, Mapping):
        return GuardResult(False, "tool arguments are not a mapping")
    touched = sorted(PROTECTED_KEYS & {str(key).lower() for key in arguments})
    if touched:
        return GuardResult(False, f"agents cannot set {', '.join(touched)}")
    if name == "mock_book" and arguments.get("confirmed"):
        return GuardResult(False, "agents cannot confirm a booking")
    return GuardResult(True, f"tool {name} allowed")


def _over_cap(plan: Any, context: Mapping[str, Any]) -> GuardResult | None:
    config = context.get("config") or {}
    try:
        cap = int(config["budget_cap"])
        cost = plan_cost(plan, config["paths"]["places"])
    except Exception as exc:
        return GuardResult(False, f"cannot check budget cap ({type(exc).__name__})")
    if cost > cap:
        return GuardResult(False, f"plan cost {cost} exceeds budget cap {cap}")
    return None


def _is_confirm_command(text: Any) -> bool:
    if not isinstance(text, str) or not text.strip():
        return False
    token = text.strip().split(maxsplit=1)[0]
    return token.split("@", 1)[0].lower() == CONFIRM_COMMAND


def _echoes_untrusted(text: str, descriptions: list[Any]) -> bool:
    lowered = text.lower()
    for description in descriptions:
        cleaned = str(description).strip().lower()
        if len(cleaned) >= MIN_ECHO_LENGTH and cleaned in lowered:
            return True
    return False


@lru_cache(maxsize=8)
def _place_costs(path: str) -> dict[str, int]:
    return {place.id: place.cost for place in load_places(path)}
