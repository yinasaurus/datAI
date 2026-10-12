"""The function Role 4 calls once per benchmark question."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Mapping

from mcp import ClientSession
from mcp.client.stdio import stdio_client

from agent.config import load_config, resolve_log_path
from agent.llm import GeminiChat
from agent.loop import run_agent
from agent.mcp_client import MCPTools, server_parameters
from interfaces.types import AnswerResult, RunConfig


def answer_question(
    question: str,
    config: RunConfig | Mapping[str, object] | None = None,
) -> AnswerResult:
    """Answer one question and return the fields Role 4 logs and scores.

    ``config`` may be a ``RunConfig`` or a dict with any of the flag names:
    ``schema_mode``, ``mode``, ``max_repairs``, ``guardrails``.
    """
    if isinstance(config, RunConfig):
        chosen = config
    elif config is None:
        chosen = load_config()
    else:
        chosen = load_config(config)
    return asyncio.run(_answer(question, chosen))


async def _answer(question: str, config: RunConfig) -> AnswerResult:
    model = GeminiChat(temperature=config.temperature, seed=config.seed, model=config.model)
    # The log should name the model that actually ran, including one set only in the environment.
    logged = RunConfig(
        schema_mode=config.schema_mode,
        mode=config.mode,
        max_repairs=config.max_repairs,
        guardrails=config.guardrails,
        temperature=config.temperature,
        seed=config.seed,
        schema_k=config.schema_k,
        model=model.model,
        log_path=config.log_path,
    )
    params = server_parameters(logged.guardrails)
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            return await run_agent(
                question,
                logged,
                model,
                MCPTools(session),
                log_path=resolve_log_path(logged),
            )
