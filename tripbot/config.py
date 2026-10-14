"""Load tripbot settings from YAML plus optional key=value overrides."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

_MISSING = object()


def load_config(path: str | Path, overrides: list[str] | None = None) -> dict[str, Any]:
    """Read a YAML config file and apply ``key=value`` overrides.

    A dotted key updates a nested mapping, for example
    ``paths.results=results/other.jsonl``. Each value is coerced to the type
    already stored for that key, so ``temperature=1`` stays an int and
    ``day_start=08:00`` stays text.
    """
    if isinstance(overrides, str):
        raise TypeError("overrides must be a list of key=value strings")

    config_path = Path(path)
    with config_path.open(encoding="utf-8") as handle:
        loaded = yaml.safe_load(handle)

    if loaded is None:
        loaded = {}
    if not isinstance(loaded, dict):
        raise ValueError(f"Config at {config_path} must be a mapping")

    for item in overrides or []:
        _apply_override(loaded, item)
    return loaded


def _apply_override(config: dict[str, Any], item: str) -> None:
    if "=" not in item:
        raise ValueError(f"Override must be key=value, got {item!r}")

    key, raw_value = item.split("=", 1)
    key = key.strip()
    raw_value = raw_value.strip()
    if not key:
        raise ValueError(f"Override must be key=value, got {item!r}")

    parts = [part.strip() for part in key.split(".")]
    if any(part == "" for part in parts):
        raise ValueError(f"Override key is empty in {key!r}")

    node = config
    for part in parts[:-1]:
        child = node.get(part)
        if child is None:
            child = {}
            node[part] = child
        if not isinstance(child, dict):
            raise ValueError(f"Cannot set {key!r}: {part!r} is not a mapping")
        node = child

    leaf = parts[-1]
    if isinstance(node.get(leaf), dict):
        raise ValueError(f"Override {key!r} would replace a mapping; use a dotted key")
    node[leaf] = _coerce(raw_value, node.get(leaf, _MISSING))


def _coerce(raw: str, existing: Any) -> Any:
    if existing is _MISSING:
        return _parse_new(raw)
    if isinstance(existing, bool):
        return _parse_bool(raw)
    if isinstance(existing, int):
        return int(raw)
    if isinstance(existing, float):
        return float(raw)
    return raw


def _parse_bool(raw: str) -> bool:
    lowered = raw.lower()
    if lowered in {"true", "yes", "on", "1"}:
        return True
    if lowered in {"false", "no", "off", "0"}:
        return False
    raise ValueError(f"Cannot read {raw!r} as a boolean")


def _parse_new(raw: str) -> Any:
    lowered = raw.lower()
    if lowered in {"true", "false"}:
        return lowered == "true"
    try:
        if any(char in raw for char in ".eE"):
            return float(raw)
        return int(raw)
    except ValueError:
        return raw
