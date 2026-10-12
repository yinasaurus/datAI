"""Shared data shapes for Role 2 and the other roles.

Teammates can import these types and depend on the field names.
Role 1 fills schema chunks. Role 3 returns a guardrail decision.
Role 4 reads the answer dictionary from ``answer_question``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, TypedDict

SchemaMode = Literal["full", "rag"]
AgentMode = Literal["single_shot", "agent_loop"]
GuardrailMode = Literal["on", "off"]


@dataclass(frozen=True)
class SchemaChunk:
    """One piece of schema context returned by the retriever.

    ``text`` is untrusted. It may quote customer reviews or other stored text.
    The agent must treat it as data, not as instructions.
    """

    id: str
    text: str
    source: str


@dataclass(frozen=True)
class GuardrailDecision:
    """What the harness says about one SQL string.

    ``allowed`` false means the MCP server must not send the SQL to PostgreSQL.
    ``reason`` is shown to the agent so a later repair attempt can explain itself.
    Role 3 replaces the function that builds this. The fields stay the same.
    """

    allowed: bool
    reason: str


@dataclass(frozen=True)
class RunConfig:
    """Switches Role 4 sets when comparing conditions.

    ``max_repairs`` is the maximum number of SQL attempts in the agent loop,
    including the first try. The proposal's "up to 3" is the default.
    ``single_shot`` ignores it and always stops after one attempt.
    ``model`` is copied from the ``GEMINI_MODEL`` environment variable.
    """

    schema_mode: str = "rag"
    mode: str = "agent_loop"
    max_repairs: int = 3
    guardrails: str = "on"
    temperature: float = 0.0
    seed: int = 42
    schema_k: int = 4
    model: str = ""
    log_path: str = "logs/runs.jsonl"

    def attempt_limit(self) -> int:
        """How many SQL writes this condition may make."""
        if self.mode == "single_shot":
            return 1
        return self.max_repairs

    def validate(self) -> None:
        if self.schema_mode not in ("full", "rag"):
            raise ValueError("schema_mode must be 'full' or 'rag'.")
        if self.mode not in ("single_shot", "agent_loop"):
            raise ValueError("mode must be 'single_shot' or 'agent_loop'.")
        if self.guardrails not in ("on", "off"):
            raise ValueError("guardrails must be 'on' or 'off'.")
        if self.max_repairs < 1:
            raise ValueError("max_repairs must be at least 1.")
        if self.schema_k < 1:
            raise ValueError("schema_k must be at least 1.")
        if not 0 <= self.temperature <= 2:
            raise ValueError("temperature must be between 0 and 2.")


class AttemptRecord(TypedDict):
    attempt: int
    sql: str
    error: str | None
    row_count: int | None


class TokenUsage(TypedDict):
    prompt: int
    completion: int
    total: int


class LLMCallRecord(TypedDict):
    step: str
    attempt: int | None
    latency_ms: float
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class AnswerResult(TypedDict):
    """Return value of ``answer_question``. Role 4 can call this in a loop."""

    answer: str
    sql: str | None
    row_count: int | None
    attempts: list[AttemptRecord]
    attempt_count: int
    succeeded_attempt: int | None
    latency_ms: float
    tokens: TokenUsage
    calls: list[LLMCallRecord]
    error: str | None
    schema_mode: str
    mode: str
    guardrails: str
    model: str


class QueryPayload(TypedDict):
    """What ``run_read_query`` returns. SQL failures set ``ok`` false and fill ``error``."""

    ok: bool
    columns: list[str]
    rows: list[list[object]]
    row_count: int
    error: str | None
