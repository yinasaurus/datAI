"""Group chat handling: profiles, plans, confirm, and cooldown.

``handle_message`` extracts updates from ordinary text, handles commands without
extraction, and warns about unsupported requirements. Outgoing text and booking both go through
``check_action``.
"""

from __future__ import annotations

import json
import logging
import re
import time
from pathlib import Path
from typing import Any

from tripbot.bot.guard_adapter import check_action
from tripbot.bot.tracker import ProfileUpdate, extract_update
from tripbot.checker.check_plan import check_plan
from tripbot.guardrails.booking import mock_book
from tripbot.planning.registry import make_plan
from tripbot.schemas import Plan, Profile, load_places, load_travel_times

logger = logging.getLogger(__name__)

TELEGRAM_LIMIT = 4096
_COMMANDS = {"plan", "itinerary", "profiles", "confirm", "acknowledge"}
_PLAN_WORDS = re.compile(r"\b(itinerary|plan|schedule)\b", re.IGNORECASE)
_CACHE: dict[str, dict[str, Any]] = {}


def handle_message(
    group_id: str,
    sender: str,
    text: str,
    config: dict[str, Any],
    *,
    client: Any = None,
    sender_id: str | None = None,
) -> str | None:
    """Update the sender profile, handle commands, and warn on unchecked requirements."""
    group, path = _group(config, group_id)
    identity = f"telegram:{sender_id}" if sender_id is not None else sender
    if sender_id is not None and not group.get("stable_identity"):
        # Names cannot safely establish ownership of old Telegram profiles.
        group["legacy_profiles"] = group.pop("profiles", {})
        group["profiles"] = {}
        group["latest_plan"] = None
        group["stable_identity"] = True
        _save(path)
    group.setdefault("display_names", {})[identity] = sender
    kind = _addressed(text, str(config.get("bot_name", "tripbot")))
    recognised_command = text.strip().startswith("/") and kind is not None
    update = None if recognised_command else extract_update(text, config, client=client)
    if update is not None:
        _merge_profile(group, identity, update)
    _save(path)
    if kind == "acknowledge":
        raw = group.get("profiles", {}).get(identity)
        if raw is not None:
            raw["acknowledged"] = list(raw.get("unsupported", []))
            _save(path)
        return _reply(group_id, sender, text, config,
                      "Acknowledged your current unsupported requirements. They remain unchecked; "
                      "acknowledgement does not mean the itinerary accommodates them.", [])
    if update is not None and update.unsupported:
        warning = _unsupported_notice(group)
        if kind is None:
            return _reply(group_id, sender, text, config, warning, [])
    if kind is None:
        return None
    if kind in {"plan", "itinerary"}:
        return _plan(group, path, group_id, sender, text, config, client)
    if kind == "profiles":
        return _reply(group_id, sender, text, config, _format_profiles(group), [])
    if kind == "confirm":
        return _confirm(group, group_id, sender, text, config)
    return None


def load_state(config: dict[str, Any]) -> dict[str, Any]:
    """Read ``data/bot_state.json`` into memory. Missing files start empty."""
    path = _state_path(config)
    key = str(path)
    if key not in _CACHE:
        _CACHE[key] = _read(path)
    return _CACHE[key]


def split_reply(text: str, limit: int = TELEGRAM_LIMIT) -> list[str]:
    """Split a reply into chunks that fit a Telegram message."""
    if len(text) <= limit:
        return [text]
    parts: list[str] = []
    current: list[str] = []
    size = 0
    for line in text.splitlines(keepends=True):
        if len(line) > limit:
            if current:
                parts.append("".join(current).rstrip("\n"))
                current = []
                size = 0
            for start in range(0, len(line), limit):
                parts.append(line[start : start + limit])
            continue
        if current and size + len(line) > limit:
            parts.append("".join(current).rstrip("\n"))
            current = [line]
            size = len(line)
        else:
            current.append(line)
            size += len(line)
    if current:
        parts.append("".join(current).rstrip("\n"))
    return [part for part in parts if part]


def _plan(
    group: dict[str, Any],
    path: Path,
    group_id: str,
    sender: str,
    text: str,
    config: dict[str, Any],
    client: Any,
) -> str | None:
    if _pending_requirements(group):
        return _reply(group_id, sender, text, config, _unsupported_notice(group), [])
    if _cooling(group, config):
        return None
    profiles = _ready_profiles(group)
    if len(profiles) < 2:
        return _reply(
            group_id,
            sender,
            text,
            config,
            "I need preferences from at least two friends before I can plan.",
            [],
        )
    try:
        places = load_places(config["paths"]["places"])
        travel = load_travel_times(config["paths"]["travel_times"])
        planner_config = dict(config)
        planner_config["days"] = int(config.get("days", 2))
        result = make_plan(
            str(config.get("setup", "A")),
            profiles,
            places,
            travel,
            planner_config,
            client=client,
        )
        report = None
        if result.plan is not None:
            report = check_plan(result.plan, profiles, places, travel, planner_config)
        reply = _format_plan(result.plan, places, report)
        if any(raw.get("unsupported") for raw in group.get("profiles", {}).values()):
            reply = _unsupported_notice(group) + "\n\n" + reply
    except Exception as exc:
        logger.warning("plan failed: %s", exc)
        return _reply(group_id, sender, text, config, "I could not build a plan.", [])

    descriptions = [place.description for place in places if place.description]
    sent = _reply(group_id, sender, text, config, reply, descriptions)
    if sent is None:
        return None
    if result.plan is not None:
        group["latest_plan"] = result.plan.model_dump()
    group["last_plan_at"] = time.time()
    _save(path)
    return sent


def _confirm(
    group: dict[str, Any],
    group_id: str,
    sender: str,
    text: str,
    config: dict[str, Any],
) -> str | None:
    if _pending_requirements(group):
        return _reply(group_id, sender, text, config, _unsupported_notice(group), [])
    stored = group.get("latest_plan")
    if not stored:
        return _reply(group_id, sender, text, config, "There is nothing to confirm.", [])
    try:
        plan = Plan.model_validate(stored)
        profiles = _ready_profiles(group)
        if len(profiles) < 2:
            return _reply(group_id, sender, text, config,
                          "I need valid budgets from at least two friends before booking.", [])
        places = load_places(config["paths"]["places"])
        travel = load_travel_times(config["paths"]["travel_times"])
        validation_config = dict(config)
        validation_config["days"] = int(config.get("days", 2))
        report = check_plan(plan, profiles, places, travel, validation_config)
        if not report.task_success:
            reasons = [item.detail for item in report.violations]
            if report.hard_limit_satisfaction < 1.0:
                reasons.append("The plan breaks a current hard limit.")
            return _reply(group_id, sender, text, config,
                          "Cannot book the latest plan: " + "; ".join(reasons), [])
    except Exception:
        logger.exception("booking validation failed")
        return _reply(group_id, sender, text, config,
                      "Cannot book: I could not validate the latest plan.", [])
    context = _context(group_id, sender, text, config, [])
    decision = check_action(
        "book",
        {"plan": stored, "confirmed": True},
        context,
    )
    if not decision.allowed:
        logger.warning("booking blocked: %s", decision.reason)
        return _reply(group_id, sender, text, config,
                      "Cannot book the latest plan: " + decision.reason, [])
    outcome = mock_book(plan, True)
    if not outcome.get("booked"):
        return _reply(group_id, sender, text, config, "I could not book the latest plan.", [])
    return _reply(group_id, sender, text, config, "Booked the latest plan.", [])


def _reply(
    group_id: str,
    sender: str,
    text: str,
    config: dict[str, Any],
    reply: str,
    descriptions: list[str],
) -> str | None:
    body = _cap(reply)
    decision = check_action(
        "reply",
        {"text": body},
        _context(group_id, sender, text, config, descriptions),
    )
    if not decision.allowed:
        logger.warning("reply blocked: %s", decision.reason)
        return None
    return body


def _context(
    group_id: str,
    sender: str,
    text: str,
    config: dict[str, Any],
    descriptions: list[str],
) -> dict[str, Any]:
    return {
        "config": config,
        "group_id": group_id,
        "sender": sender,
        "chat_text": text,
        "place_descriptions": descriptions,
    }


def _addressed(text: str, bot_name: str) -> str | None:
    stripped = text.strip()
    if not stripped:
        return None
    token = stripped.split(maxsplit=1)[0]
    if token.startswith("/"):
        name = token[1:].split("@", 1)[0].lower()
        if name in _COMMANDS:
            return name
    if bot_name and _names_bot(stripped, bot_name) and _PLAN_WORDS.search(stripped):
        return "plan"
    return None


def _names_bot(text: str, bot_name: str) -> bool:
    pattern = rf"(?<!\w){re.escape(bot_name)}(?!\w)"
    return re.search(pattern, text, flags=re.IGNORECASE) is not None


def _cooling(group: dict[str, Any], config: dict[str, Any]) -> bool:
    last = group.get("last_plan_at")
    if last is None:
        return False
    wait = float(config.get("cooldown_seconds", 20))
    return time.time() - float(last) < wait


def _merge_profile(group: dict[str, Any], sender: str, update: ProfileUpdate) -> None:
    profiles = group.setdefault("profiles", {})
    stored = profiles.get(sender) or {"likes": [], "hard_limits": [], "budget": None}
    def revised(old: list[str], added: list[str], removed: list[str]) -> list[str]:
        return [name for name in dict.fromkeys(old + added) if name not in removed]

    unsupported = revised(stored.get("unsupported", []), update.unsupported, update.remove_unsupported)
    profiles[sender] = {
        "likes": revised(stored["likes"], update.likes, update.remove_likes),
        "hard_limits": revised(stored["hard_limits"], update.hard_limits, update.remove_hard_limits),
        "budget": update.budget if update.budget is not None else stored.get("budget"),
        "unsupported": unsupported,
        "acknowledged": [name for name in stored.get("acknowledged", [])
                         if name in unsupported and name not in update.unsupported],
    }


def _pending_requirements(group: dict[str, Any]) -> bool:
    return any(
        (set(raw.get("unsupported", [])) - set(raw.get("acknowledged", [])))
        & {"dietary", "accessibility"}
        for raw in group.get("profiles", {}).values()
    )


def _unsupported_notice(group: dict[str, Any]) -> str:
    categories = sorted({name for raw in group.get("profiles", {}).values()
                         for name in raw.get("unsupported", [])})
    body = "The bot cannot check these requirements: " + ", ".join(categories) + "."
    if _pending_requirements(group):
        body += (" Planning and booking are paused. Each affected person must send /acknowledge "
                 "to accept that their dietary or accessibility requirements remain unchecked, "
                 "or explicitly withdraw the requirement.")
    else:
        body += " These requirements remain unchecked in any itinerary."
    return body


def _ready_profiles(group: dict[str, Any]) -> dict[str, Profile]:
    ready: dict[str, Profile] = {}
    for name, raw in group.get("profiles", {}).items():
        budget = raw.get("budget")
        if not isinstance(budget, int) or budget <= 0:
            continue
        label = group.get("display_names", {}).get(name, name)
        key = f"{label} ({name})" if name.startswith("telegram:") else name
        ready[key] = Profile(
            likes=list(raw.get("likes") or []),
            hard_limits=list(raw.get("hard_limits") or []),
            budget=budget,
        )
    return ready


def _format_profiles(group: dict[str, Any]) -> str:
    profiles = group.get("profiles") or {}
    if not profiles:
        if group.get("legacy_profiles"):
            return "Older profiles were archived because their owners could not be verified. Please share preferences again."
        return "No profiles yet."
    lines = ["Profiles:"]
    for name in sorted(profiles):
        raw = profiles[name]
        likes = ", ".join(raw.get("likes") or []) or "none"
        limits = ", ".join(raw.get("hard_limits") or []) or "none"
        budget = raw.get("budget")
        budget_text = str(budget) if isinstance(budget, int) else "unset"
        label = group.get("display_names", {}).get(name, name)
        lines.append(f"{label}: likes {likes}; limits {limits}; budget {budget_text} SGD per person for the trip")
        if raw.get("unsupported"):
            lines.append("Unchecked requirements: " + ", ".join(raw["unsupported"]))
    if group.get("legacy_profiles"):
        lines.append("Older profiles were archived because their owners could not be verified. Please share preferences again.")
    return "\n".join(lines)


def _format_plan(plan: Plan | None, places: list[Any], report: Any) -> str:
    names = {place.id: place.name for place in places}
    costs = {place.id: place.cost for place in places}
    lines: list[str] = []
    total = 0
    if plan is None:
        lines.append("I could not build a plan.")
    else:
        for day in plan.days:
            lines.append(f"Day {day.day}")
            for item in day.items:
                lines.append(f"{item.start}-{item.end} {names.get(item.place_id, item.place_id)}")
                total += int(costs.get(item.place_id, 0))
        lines.append(f"Cost per person: {total}")
    if report is None or not report.violations:
        lines.append("Violations: none")
    else:
        lines.append("Violations:")
        for item in report.violations:
            detail = f": {item.detail}" if item.detail else ""
            lines.append(f"- {item.type}{detail}")
    return "\n".join(lines)


def _cap(text: str, limit: int = TELEGRAM_LIMIT) -> str:
    if len(text) <= limit:
        return text
    cut = text[: limit - 1]
    newline = cut.rfind("\n")
    if newline > 0:
        cut = cut[:newline]
    return cut + "…"


def _group(config: dict[str, Any], group_id: str) -> tuple[dict[str, Any], Path]:
    root = load_state(config)
    groups = root.setdefault("groups", {})
    group = groups.setdefault(
        group_id,
        {"profiles": {}, "latest_plan": None, "last_plan_at": None},
    )
    return group, _state_path(config)


def _state_path(config: dict[str, Any]) -> Path:
    paths = config.get("paths") or {}
    return Path(str(paths.get("bot_state", "data/bot_state.json")))


def _read(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {"groups": {}}
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("state file ignored: %s", exc)
        return {"groups": {}}
    if not isinstance(loaded, dict):
        return {"groups": {}}
    loaded.setdefault("groups", {})
    return loaded


def _save(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(_CACHE[str(path)], indent=2)
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(payload, encoding="utf-8")
    temporary.replace(path)
