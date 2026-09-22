"""Natural-language questions over the Northline database.

``ask`` retrieves schema, writes SQL, runs it through the MCP server, retries
up to three times, then summarizes the rows. Each call is appended to
``agent/logs/runs.jsonl``.
"""

from agent.loop import MAX_ATTEMPTS, ask

__all__ = ["MAX_ATTEMPTS", "ask"]
