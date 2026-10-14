"""Tests for scripts/validate_places.py."""

import json
from pathlib import Path

from scripts.validate_places import main, validate_places
from tripbot.schemas import load_places, load_tag_catalog, load_travel_times

ROOT = Path(__file__).resolve().parents[1]


def _write_places(path: Path, rows: list[dict[str, object]]) -> Path:
    path.write_text(json.dumps(rows), encoding="utf-8")
    return path


def _row(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "id": "p01",
        "name": "PLACEHOLDER 01",
        "tags": ["food"],
        "cost": 10,
        "opens": "10:00",
        "closes": "18:00",
        "area": "centre",
        "duration_min": 60,
        "source": "TODO",
        "verified": False,
    }
    base.update(overrides)
    return base


def test_shipped_places_are_placeholders() -> None:
    places = load_places(ROOT / "data" / "places.json")
    catalog = load_tag_catalog(ROOT / "data" / "tags.json")
    travel = load_travel_times(ROOT / "data" / "travel_times.json")

    assert len(places) == 25
    assert len(catalog.tags) == 8
    assert set(catalog.hard_limits) == {"no_temples", "no_early_mornings", "no_nightlife"}
    assert travel.areas == ["centre", "north", "east", "south", "west"]
    assert {place.area for place in places} == set(travel.areas)
    assert all(place.verified is False for place in places)
    assert all(place.source == "TODO" for place in places)
    assert all(place.name.startswith("PLACEHOLDER") for place in places)
    assert validate_places(
        ROOT / "data" / "places.json",
        ROOT / "data" / "tags.json",
        ROOT / "data" / "travel_times.json",
    ) == []


def test_unknown_tag_fails(tmp_path: Path) -> None:
    path = _write_places(tmp_path / "places.json", [_row(tags=["spa"])])

    problems = validate_places(
        path,
        ROOT / "data" / "tags.json",
        ROOT / "data" / "travel_times.json",
    )

    assert problems == ["p01: unknown tags spa"]


def test_require_verified_fails_until_every_row_is_verified(tmp_path: Path) -> None:
    tags = ROOT / "data" / "tags.json"
    travel = ROOT / "data" / "travel_times.json"
    unverified = _write_places(tmp_path / "places.json", [_row(verified=False)])

    assert validate_places(unverified, tags, travel, require_verified=True) == [
        "p01: verified is false"
    ]
    assert main(["--places", str(unverified), "--require-verified"]) == 1

    verified = _write_places(tmp_path / "verified.json", [_row(verified=True, source="https://example.com")])
    assert validate_places(verified, tags, travel, require_verified=True) == []


def test_duplicate_id_and_unknown_area_fail(tmp_path: Path) -> None:
    path = _write_places(
        tmp_path / "places.json",
        [_row(id="p01"), _row(id="p01", area="island")],
    )

    problems = validate_places(
        path,
        ROOT / "data" / "tags.json",
        ROOT / "data" / "travel_times.json",
    )

    assert "p01: duplicate place id" in problems
    assert "p01: unknown area island" in problems


def test_shipped_places_fail_the_verified_flag() -> None:
    assert main(["--require-verified"]) == 1
    assert main([]) == 0
