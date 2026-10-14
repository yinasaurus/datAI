"""Call the guardrails teammate's ``guard`` without owning that package.

``check_action`` builds one action dict and passes the caller's context through.
It calls ``tripbot.guardrails.guard.guard`` only when ``context["config"]["guardrails"]``
is ``"on"`` and that function is a real implementation. If the module is missing,
the function is absent, it raises ``NotImplementedError``, or it returns nothing,
the action is allowed and one warning is logged. ``guardrails: off`` does the same
without calling ``guard``.
"""

from __future__ import annotations

import importlib
import logging
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

ACTION_TYPES = ("reply", "book", "tool_call")


@dataclass(frozen=True)
class GuardResult:
    """Whether an action may proceed, and a short reason."""

    allowed: bool
    reason: str


def check_action(action_type: str, payload: Any, context: dict[str, Any]) -> GuardResult:
    """Allow, or ask ``guard(action, context)`` when guardrails are on.

    ``action`` is ``{"type": action_type, "payload": payload}``. ``context`` is
    passed through unchanged. ``payload`` shapes:

    - ``reply``: ``{"text": str}``
    - ``book``: ``{"plan": dict, "confirmed": bool}``
    - ``tool_call``: ``{"name": str, "arguments": dict}``
      with ``name`` one of ``search_places``, ``check_plan``, ``mock_book``
    """
    if not _guardrails_on(context):
        logger.warning("guardrails are off; allowing %s", action_type)
        return GuardResult(True, "guardrails off")

    function, problem = _load_guard()
    if function is None:
        logger.warning("%s; allowing %s", problem, action_type)
        return GuardResult(True, "guard unavailable")

    action = {"type": action_type, "payload": payload}
    try:
        raw = function(action, context)
    except NotImplementedError:
        logger.warning("guard is still a stub; allowing %s", action_type)
        return GuardResult(True, "guard unavailable")
    except Exception as exc:
        logger.warning("guard raised %s; blocking %s", type(exc).__name__, action_type)
        return GuardResult(False, f"guard error: {type(exc).__name__}")

    result = _as_result(raw)
    if result is None:
        logger.warning("guard returned no decision; allowing %s", action_type)
        return GuardResult(True, "guard unavailable")
    return result


def _guardrails_on(context: Mapping[str, Any]) -> bool:
    config = context.get("config")
    if not isinstance(config, Mapping):
        return False
    value = config.get("guardrails", "off")
    if isinstance(value, str):
        return value.strip().lower() == "on"
    return value is True


def _load_guard() -> tuple[Callable[..., Any] | None, str | None]:
    try:
        module = importlib.import_module("tripbot.guardrails.guard")
    except Exception as exc:
        return None, f"guard module unavailable ({type(exc).__name__}: {exc})"
    function = getattr(module, "guard", None)
    if not callable(function):
        return None, "guard module has no guard function"
    return function, None


def _as_result(raw: Any) -> GuardResult | None:
    if isinstance(raw, GuardResult):
        return raw
    allowed: Any
    reason: Any
    if isinstance(raw, Mapping):
        allowed = raw.get("allowed")
        reason = raw.get("reason")
    else:
        allowed = getattr(raw, "allowed", None)
        reason = getattr(raw, "reason", None)
    if isinstance(allowed, bool) and isinstance(reason, str):
        return GuardResult(allowed, reason)
    return None
