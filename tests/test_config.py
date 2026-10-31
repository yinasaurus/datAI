"""Tests for load_config."""

from pathlib import Path

import pytest

from tripbot.config import load_config

ROOT = Path(__file__).resolve().parents[1]

_SAMPLE = """
model: REPLACE_WITH_EXACT_MODEL_NAME
temperature: 0
seed: 42
cache: true
setup: C
guardrails: "on"
day_start: "07:00"
breaking_point_threshold: 0.5
paths:
  places: data/places.json
  results: results/runs.jsonl
"""


def test_shipped_config_loads() -> None:
    config = load_config(ROOT / "config.yaml", [])

    assert isinstance(config["model"], str) and config["model"].strip()
    assert config["temperature"] == 0
    assert config["seed"] == 42
    assert config["cache"] is True
    assert config["setup"] == "C"
    assert config["days"] == 2
    assert config["min_activities_per_day"] == 2
    assert config["guardrails"] == "on"
    assert config["day_start"] == "07:00"
    assert config["day_end"] == "23:00"
    assert config["breaking_point_threshold"] == 0.5
    assert config["paths"]["places"] == "data/places.json"
    assert config["paths"]["llm_log"] == "logs/llm_calls.jsonl"


def test_study_settings_can_be_overridden_from_the_command_line() -> None:
    config = load_config(
        ROOT / "config.yaml",
        [
            "max_revisions=0",
            "negotiation_rounds=3",
            "model=test-model",
            "setup=B",
            "guardrails=off",
        ],
    )

    assert config["max_revisions"] == 0
    assert isinstance(config["max_revisions"], int)
    assert config["negotiation_rounds"] == 3
    assert isinstance(config["negotiation_rounds"], int)
    assert config["model"] == "test-model"
    assert config["setup"] == "B"
    assert config["guardrails"] == "off"


def test_overrides_coerce_to_existing_types(tmp_path: Path) -> None:
    path = tmp_path / "config.yaml"
    path.write_text(_SAMPLE, encoding="utf-8")

    config = load_config(
        path,
        [
            "temperature=1",
            "cache=false",
            "breaking_point_threshold=0.8",
            "day_start=08:00",
            "guardrails=off",
            "setup=A",
        ],
    )

    assert config["temperature"] == 1
    assert isinstance(config["temperature"], int)
    assert config["cache"] is False
    assert config["breaking_point_threshold"] == 0.8
    assert isinstance(config["breaking_point_threshold"], float)
    assert config["day_start"] == "08:00"
    assert config["guardrails"] == "off"
    assert config["setup"] == "A"


def test_dotted_override_updates_nested_value(tmp_path: Path) -> None:
    path = tmp_path / "config.yaml"
    path.write_text(_SAMPLE, encoding="utf-8")

    config = load_config(path, ["paths.results=results/dev.jsonl"])

    assert config["paths"]["results"] == "results/dev.jsonl"
    assert config["paths"]["places"] == "data/places.json"


def test_later_override_wins(tmp_path: Path) -> None:
    path = tmp_path / "config.yaml"
    path.write_text(_SAMPLE, encoding="utf-8")

    config = load_config(path, ["temperature=1", "temperature=2"])

    assert config["temperature"] == 2


def test_none_overrides_leave_file_unchanged(tmp_path: Path) -> None:
    path = tmp_path / "config.yaml"
    path.write_text(_SAMPLE, encoding="utf-8")

    config = load_config(path, None)

    assert config["setup"] == "C"
    assert config["seed"] == 42


def test_override_without_equals_raises(tmp_path: Path) -> None:
    path = tmp_path / "config.yaml"
    path.write_text(_SAMPLE, encoding="utf-8")

    with pytest.raises(ValueError, match="key=value"):
        load_config(path, ["temperature"])


def test_replacing_a_mapping_requires_a_dotted_key(tmp_path: Path) -> None:
    path = tmp_path / "config.yaml"
    path.write_text(_SAMPLE, encoding="utf-8")

    with pytest.raises(ValueError, match="dotted key"):
        load_config(path, ["paths=data/places.json"])


def test_string_overrides_argument_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "config.yaml"
    path.write_text(_SAMPLE, encoding="utf-8")

    with pytest.raises(TypeError):
        load_config(path, "temperature=1")  # type: ignore[arg-type]
