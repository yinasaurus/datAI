"""Load the evaluation switches from the environment and from Role 4's dict."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Mapping

from dotenv import load_dotenv

from interfaces.types import RunConfig

ROOT = Path(__file__).resolve().parents[1]


def load_config(overrides: Mapping[str, object] | None = None) -> RunConfig:
    """Build a ``RunConfig``. Values in ``overrides`` win over ``role2/.env``."""
    load_dotenv(ROOT / ".env")
    values: dict[str, object] = {
        "schema_mode": os.environ.get("SCHEMA_MODE", "rag"),
        "mode": os.environ.get("AGENT_MODE", "agent_loop"),
        "max_repairs": int(os.environ.get("MAX_REPAIRS", "3")),
        "guardrails": os.environ.get("GUARDRAILS", "on"),
        "temperature": float(os.environ.get("TEMPERATURE", "0")),
        "seed": int(os.environ.get("SEED", "42")),
        "schema_k": int(os.environ.get("SCHEMA_K", "4")),
        "model": os.environ.get("GEMINI_MODEL", "").strip(),
        "log_path": os.environ.get("LOG_PATH", "logs/runs.jsonl"),
    }
    if overrides:
        values.update(dict(overrides))
    config = RunConfig(
        schema_mode=str(values["schema_mode"]),
        mode=str(values["mode"]),
        max_repairs=int(values["max_repairs"]),
        guardrails=str(values["guardrails"]),
        temperature=float(values["temperature"]),
        seed=int(values["seed"]),
        schema_k=int(values["schema_k"]),
        model=str(values["model"]),
        log_path=str(values["log_path"]),
    )
    config.validate()
    return config


def resolve_log_path(config: RunConfig) -> Path:
    """Turn the configured log path into a file under this role folder."""
    path = Path(config.log_path)
    if not path.is_absolute():
        path = ROOT / path
    return path
