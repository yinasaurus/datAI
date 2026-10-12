"""Guardrail hook. Role 3 replaces ``check_sql``. Role 2 only calls it.

The MCP server calls ``check_sql`` before every execution when the eval flag
``guardrails`` is ``on``. When the flag is ``off``, the server skips this
function. That is the RQ3 ablation, and it is not a tool argument the model
can set.
"""

from __future__ import annotations

from interfaces.types import GuardrailDecision


def check_sql(sql: str) -> GuardrailDecision:
    """Allow every statement. Role 3 replaces this with the real harness.

    The real check should cover SELECT-only SQL, table and column allow-lists,
    row limits, timeouts, and the cost check. Return ``allowed=False`` and a
    short ``reason`` to block a statement. The reason is given back to the agent.
    """
    del sql
    return GuardrailDecision(allowed=True, reason="")
