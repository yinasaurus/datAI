"""Check places.json against the schema, the tag list, and travel areas."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pydantic import ValidationError

from tripbot.config import load_config
from tripbot.schemas import Place, TagCatalog, TravelTimes, read_json


def validate_places(
    places_path: Path,
    tags_path: Path,
    travel_path: Path,
    *,
    require_verified: bool = False,
) -> list[str]:
    """Return human-readable problems. An empty list means the file is valid.

    ``description`` may be omitted. The place model stores that as an empty string.
    """
    try:
        catalog = TagCatalog.model_validate(read_json(tags_path))
        travel = TravelTimes.model_validate(read_json(travel_path))
        raw = read_json(places_path)
    except ValidationError as exc:
        return [_format_validation_error(exc)]
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        return [str(exc)]

    if not isinstance(raw, list):
        return ["places file must be a list"]

    problems: list[str] = []
    seen: set[str] = set()
    for index, row in enumerate(raw):
        label = _row_label(row, index)
        try:
            place = Place.model_validate(row)
        except ValidationError as exc:
            problems.append(f"{label}: {_format_validation_error(exc)}")
            continue
        if place.id in seen:
            problems.append(f"{place.id}: duplicate place id")
        seen.add(place.id)
        unknown = [tag for tag in place.tags if tag not in catalog.tags]
        if unknown:
            problems.append(f"{place.id}: unknown tags {', '.join(unknown)}")
        if place.area not in travel.areas:
            problems.append(f"{place.id}: unknown area {place.area}")
        if require_verified and not place.verified:
            problems.append(f"{place.id}: verified is false")
    return problems


def _row_label(row: Any, index: int) -> str:
    if isinstance(row, dict) and isinstance(row.get("id"), str) and row["id"]:
        return row["id"]
    return f"row {index}"


def _format_validation_error(exc: ValidationError) -> str:
    parts: list[str] = []
    for error in exc.errors():
        loc = ".".join(str(item) for item in error["loc"])
        parts.append(f"{loc}: {error['msg']}" if loc else error["msg"])
    return "; ".join(parts)


def main(argv: list[str] | None = None) -> int:
    """Validate the places file. ``--require-verified`` fails on any unverified row."""
    config = load_config(ROOT / "config.yaml", [])
    parser = argparse.ArgumentParser(description="Validate data/places.json")
    parser.add_argument("--places", type=Path, default=ROOT / config["paths"]["places"])
    parser.add_argument("--tags", type=Path, default=ROOT / config["paths"]["tags"])
    parser.add_argument(
        "--travel-times",
        type=Path,
        default=ROOT / config["paths"]["travel_times"],
    )
    parser.add_argument(
        "--require-verified",
        action="store_true",
        help="fail when any place has verified false",
    )
    args = parser.parse_args(argv)
    problems = validate_places(
        args.places,
        args.tags,
        args.travel_times,
        require_verified=args.require_verified,
    )
    if problems:
        for problem in problems:
            print(problem)
        return 1
    print(f"ok {args.places}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
