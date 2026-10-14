"""Pydantic models for places, scenarios, plans, and check reports."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

_TIME = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")


def parse_hhmm(value: str) -> int:
    """Convert a 24-hour ``HH:MM`` string to minutes after midnight."""
    match = _TIME.fullmatch(value)
    if match is None:
        raise ValueError(f"time must be HH:MM, got {value!r}")
    return int(match.group(1)) * 60 + int(match.group(2))


def _check_hhmm(value: str) -> str:
    parse_hhmm(value)
    return value


class HardLimit(BaseModel):
    """One rule from tags.json. ``forbid_tag`` uses ``tag``; ``earliest_start`` uses ``time``."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["forbid_tag", "earliest_start"]
    tag: str | None = None
    time: str | None = None

    @model_validator(mode="after")
    def fields_match_type(self) -> HardLimit:
        if self.type == "forbid_tag":
            if not self.tag:
                raise ValueError("forbid_tag needs a tag")
            if self.time is not None:
                raise ValueError("forbid_tag does not use time")
        else:
            if self.time is None:
                raise ValueError("earliest_start needs a time")
            parse_hhmm(self.time)
            if self.tag is not None:
                raise ValueError("earliest_start does not use a tag")
        return self


class TagCatalog(BaseModel):
    """The shared vocabulary. Every tag and hard limit used elsewhere must appear here."""

    model_config = ConfigDict(extra="forbid")

    tags: list[str] = Field(min_length=1)
    hard_limits: dict[str, HardLimit]

    @model_validator(mode="after")
    def limits_use_known_tags(self) -> TagCatalog:
        if len(set(self.tags)) != len(self.tags):
            raise ValueError("duplicate tag in vocabulary")
        for name, rule in self.hard_limits.items():
            if not name:
                raise ValueError("hard limit name is empty")
            if rule.type == "forbid_tag" and rule.tag not in self.tags:
                raise ValueError(f"{name} forbids unknown tag {rule.tag}")
        return self


class Place(BaseModel):
    """One visitable place. Placeholder rows stay unverified until a person sources them."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    description: str = ""
    tags: list[str] = Field(min_length=1)
    cost: int = Field(ge=0)
    opens: str
    closes: str
    area: str = Field(min_length=1)
    duration_min: int = Field(gt=0)
    source: str = Field(min_length=1)
    verified: bool

    @field_validator("opens", "closes")
    @classmethod
    def times_are_hhmm(cls, value: str) -> str:
        return _check_hhmm(value)

    @field_validator("tags")
    @classmethod
    def tags_are_unique(cls, value: list[str]) -> list[str]:
        if any(not tag for tag in value):
            raise ValueError("tag is empty")
        if len(set(value)) != len(value):
            raise ValueError("duplicate tag")
        return value

    @model_validator(mode="after")
    def window_can_hold_a_visit(self) -> Place:
        open_min = parse_hhmm(self.opens)
        close_min = parse_hhmm(self.closes)
        if close_min <= open_min:
            raise ValueError("closes must be after opens")
        if self.duration_min > close_min - open_min:
            raise ValueError("duration_min is longer than the opening window")
        return self


class TravelTimes(BaseModel):
    """Symmetric minutes between areas. Each unordered pair is stored once."""

    model_config = ConfigDict(extra="forbid")

    areas: list[str] = Field(min_length=1)
    minutes: dict[str, dict[str, int]]
    same_area_minutes: int = Field(ge=0)

    @model_validator(mode="after")
    def pairs_cover_every_area(self) -> TravelTimes:
        if any(not area for area in self.areas):
            raise ValueError("area name is empty")
        if len(set(self.areas)) != len(self.areas):
            raise ValueError("duplicate area")
        known = set(self.areas)
        seen: dict[tuple[str, str], int] = {}
        for origin, destinations in self.minutes.items():
            if origin not in known:
                raise ValueError(f"unknown area {origin}")
            for destination, minutes in destinations.items():
                if destination not in known:
                    raise ValueError(f"unknown area {destination}")
                if destination == origin:
                    raise ValueError("same-area time belongs in same_area_minutes")
                if minutes < 0:
                    raise ValueError("travel minutes must be >= 0")
                key = tuple(sorted((origin, destination)))
                if key in seen and seen[key] != minutes:
                    raise ValueError(f"asymmetric travel time for {key[0]} and {key[1]}")
                seen[key] = minutes
        expected = {
            tuple(sorted((left, right)))
            for index, left in enumerate(self.areas)
            for right in self.areas[index + 1 :]
        }
        missing = expected - set(seen)
        if missing:
            pairs = ", ".join(f"{left}-{right}" for left, right in sorted(missing))
            raise ValueError(f"missing travel pairs: {pairs}")
        return self

    def travel_minutes(self, area_a: str, area_b: str) -> int:
        """Return minutes from ``area_a`` to ``area_b``. The lookup is symmetric."""
        if area_a not in self.areas or area_b not in self.areas:
            raise KeyError(f"unknown area in travel lookup: {area_a!r}, {area_b!r}")
        if area_a == area_b:
            return self.same_area_minutes
        direct = self.minutes.get(area_a, {}).get(area_b)
        if direct is not None:
            return direct
        reverse = self.minutes.get(area_b, {}).get(area_a)
        if reverse is None:
            raise KeyError(f"no travel time for {area_a} and {area_b}")
        return reverse


def travel_minutes(travel_times: TravelTimes, area_a: str, area_b: str) -> int:
    """Return minutes between two areas. Same area uses ``same_area_minutes``."""
    return travel_times.travel_minutes(area_a, area_b)


def place_fits(place: Place, earliest: str, day_end: str) -> bool:
    """Return whether one visit fits in the place hours and the day window."""
    start = max(parse_hhmm(earliest), parse_hhmm(place.opens))
    end = start + place.duration_min
    return end <= parse_hhmm(place.closes) and end <= parse_hhmm(day_end)


class Profile(BaseModel):
    """One friend's likes, hard limits, and whole-trip budget."""

    model_config = ConfigDict(extra="forbid")

    likes: list[str]
    hard_limits: list[str]
    budget: int = Field(ge=0)

    @field_validator("likes", "hard_limits")
    @classmethod
    def names_are_unique(cls, value: list[str]) -> list[str]:
        if any(not item for item in value):
            raise ValueError("empty name")
        if len(set(value)) != len(value):
            raise ValueError("duplicate entry")
        return value


class Scenario(BaseModel):
    """A group, a trip length, and the factors the study balances."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    split: Literal["dev", "heldout"]
    days: int = Field(ge=1, le=7)
    n_friends: Literal[2, 3, 5]
    conflict: Literal["mild", "strong"]
    budget: Literal["loose", "tight"]
    friends: dict[str, Profile]

    @model_validator(mode="after")
    def friend_count_matches(self) -> Scenario:
        if any(not name for name in self.friends):
            raise ValueError("friend name is empty")
        if len(self.friends) != self.n_friends:
            raise ValueError("n_friends must match the number of friends")
        return self


class PlanItem(BaseModel):
    """One visit. ``start`` and ``end`` are 24-hour HH:MM strings."""

    model_config = ConfigDict(extra="forbid")

    place_id: str = Field(min_length=1)
    start: str
    end: str

    @field_validator("start", "end")
    @classmethod
    def times_are_hhmm(cls, value: str) -> str:
        return _check_hhmm(value)

    @model_validator(mode="after")
    def end_after_start(self) -> PlanItem:
        if parse_hhmm(self.end) <= parse_hhmm(self.start):
            raise ValueError("end must be after start")
        return self


class PlanDay(BaseModel):
    """The visits on one day of a plan."""

    model_config = ConfigDict(extra="forbid")

    day: int = Field(ge=1)
    items: list[PlanItem]


class Plan(BaseModel):
    """A multi-day itinerary. The checker decides whether the times are legal."""

    model_config = ConfigDict(extra="forbid")

    days: list[PlanDay]


class Violation(BaseModel):
    """One feasibility failure. Stats count rows by ``type``."""

    model_config = ConfigDict(extra="forbid")

    type: Literal[
        "unknown_place",
        "closed",
        "too_short",
        "overlap",
        "travel_gap",
        "over_budget",
    ]
    detail: str = ""


class Fairness(BaseModel):
    """Spread of per-friend satisfaction. ``gap`` is max minus min."""

    model_config = ConfigDict(extra="forbid")

    min: float = Field(ge=0, le=1)
    gap: float = Field(ge=0, le=1)
    jain: float = Field(ge=0, le=1)


class Report(BaseModel):
    """Result of ``check_plan``. ``task_success`` needs feasibility and every hard limit."""

    model_config = ConfigDict(extra="forbid")

    feasible: bool
    violations: list[Violation]
    hard_limit_satisfaction: float = Field(ge=0, le=1)
    per_friend_satisfaction: dict[str, float]
    fairness: Fairness
    task_success: bool

    @field_validator("per_friend_satisfaction")
    @classmethod
    def scores_are_fractions(cls, value: dict[str, float]) -> dict[str, float]:
        for name, score in value.items():
            if not name:
                raise ValueError("friend name is empty")
            if not 0 <= score <= 1:
                raise ValueError(f"satisfaction for {name} must be between 0 and 1")
        return value

    @model_validator(mode="after")
    def flags_match_the_spec(self) -> Report:
        if self.violations and self.feasible:
            raise ValueError("feasible must be false when any violation is listed")
        if not self.feasible and not self.violations:
            raise ValueError("a failed plan must list at least one violation")
        expected = self.feasible and self.hard_limit_satisfaction == 1.0
        if self.task_success is not expected:
            raise ValueError(
                "task_success must be true only when the plan is feasible "
                "and hard_limit_satisfaction is 1"
            )
        return self


def read_json(path: str | Path) -> Any:
    """Load one JSON file as a Python object."""
    with Path(path).open(encoding="utf-8") as handle:
        return json.load(handle)


def load_tag_catalog(path: str | Path) -> TagCatalog:
    """Validate tags.json."""
    return TagCatalog.model_validate(read_json(path))


def load_places(path: str | Path) -> list[Place]:
    """Validate places.json and reject duplicate ids."""
    raw = read_json(path)
    if not isinstance(raw, list):
        raise ValueError("places file must be a list")
    places = [Place.model_validate(row) for row in raw]
    seen: set[str] = set()
    duplicates: set[str] = set()
    for place in places:
        if place.id in seen:
            duplicates.add(place.id)
        seen.add(place.id)
    if duplicates:
        raise ValueError(f"duplicate place ids: {', '.join(sorted(duplicates))}")
    return places


def load_travel_times(path: str | Path) -> TravelTimes:
    """Validate travel_times.json."""
    return TravelTimes.model_validate(read_json(path))


def load_scenario(path: str | Path) -> Scenario:
    """Validate one scenario file."""
    return Scenario.model_validate(read_json(path))
