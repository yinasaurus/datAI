"""Speak to the three MCP tools over stdio.

One server process handles one question: schema lookup and every SQL attempt
share it. ``GUARDRAILS`` is set on that process from the run config.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.types import CallToolResult, TextContent

from interfaces.types import QueryPayload

ROOT = Path(__file__).resolve().parents[1]
SERVER = ROOT / "mcp_server" / "server.py"


class MCPTools:
    """Sync wrapper around one MCP session. Used by ``answer_question``."""

    def __init__(self, session: ClientSession) -> None:
        self._session = session

    async def get_full_schema(self) -> dict:
        return await self._call("get_full_schema", {})

    async def retrieve_schema(self, question: str, k: int) -> dict:
        return await self._call("retrieve_schema", {"question": question, "k": k})

    async def run_read_query(self, sql: str) -> QueryPayload:
        data = await self._call("run_read_query", {"sql": sql})
        if "ok" not in data:
            return {
                "ok": False,
                "columns": [],
                "rows": [],
                "row_count": 0,
                "error": "The query tool returned an unexpected payload.",
            }
        return data  # type: ignore[return-value]

    async def _call(self, name: str, arguments: dict) -> dict:
        result = await self._session.call_tool(name, arguments)
        if result.isError:
            return {
                "ok": False,
                "text": "",
                "error": _tool_text(result) or f"Tool {name} failed.",
                "columns": [],
                "rows": [],
                "row_count": 0,
            }
        return _tool_data(result)


def server_parameters(guardrails: str) -> StdioServerParameters:
    """Start ``server.py`` with the guardrail flag for this question."""
    env = os.environ.copy()
    env["GUARDRAILS"] = guardrails
    return StdioServerParameters(
        command=sys.executable,
        args=["-u", str(SERVER)],
        cwd=str(ROOT),
        env=env,
    )


def _tool_text(result: CallToolResult) -> str:
    parts: list[str] = []
    for block in result.content:
        if isinstance(block, TextContent):
            parts.append(block.text)
    return "\n".join(parts).strip()


def _tool_data(result: CallToolResult) -> dict:
    if result.structuredContent is not None:
        data = result.structuredContent
    else:
        data = json.loads(_tool_text(result))
    if isinstance(data, dict) and isinstance(data.get("result"), dict):
        nested = data["result"]
        if "text" in nested or "ok" in nested or "rows" in nested:
            return nested
    return data
