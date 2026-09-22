"""Connect to the Northline MCP server over stdio and call each tool.

Run from the project root with the interpreter that has the MCP SDK installed:

    python mcp_server/test_client.py
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.types import CallToolResult, TextContent

ROOT = Path(__file__).resolve().parents[1]
SERVER = ROOT / "mcp_server" / "server.py"


def _text(result: CallToolResult) -> str:
    parts: list[str] = []
    for block in result.content:
        if isinstance(block, TextContent):
            parts.append(block.text)
    return "\n".join(parts)


def _data(result: CallToolResult) -> dict:
    if result.structuredContent is not None:
        return result.structuredContent
    return json.loads(_text(result))


async def main() -> int:
    failures: list[str] = []

    def check(ok: bool, label: str) -> None:
        print(f"{'ok  ' if ok else 'FAIL'} {label}")
        if not ok:
            failures.append(label)

    params = StdioServerParameters(
        command=sys.executable,
        args=["-u", str(SERVER)],
        cwd=str(ROOT),
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            listed = await session.list_tools()
            names = sorted(tool.name for tool in listed.tools)
            check(names == ["describe_table", "list_tables", "run_read_query"], f"tools {names}")

            tables_result = await session.call_tool("list_tables", {})
            check(not tables_result.isError, "list_tables succeeded")
            tables = _data(tables_result)["tables"]
            table_names = {item["name"] for item in tables}
            print(f"     list_tables -> {len(tables)} objects")
            check("students" in table_names and "faculty" in table_names, "students and faculty are listed")
            check(any(item["name"] == "current_term" and item["type"] == "view" for item in tables), "current_term view is listed")

            described = await session.call_tool("describe_table", {"table_name": "students"})
            check(not described.isError, "describe_table(students) succeeded")
            student_columns = {column["name"] for column in _data(described)["columns"]}
            print(f"     describe_table(students) -> {len(student_columns)} columns")
            check({"student_id", "major_department_id"} <= student_columns, "students columns include keys")
            check("ssn" not in student_columns, "ssn is hidden by guardrails")
            fks = _data(described)["foreign_keys"]
            check(any(fk["column"] == "major_department_id" and fk["references_table"] == "departments" for fk in fks), "major foreign key is described")

            missing = await session.call_tool("describe_table", {"table_name": "not_a_table"})
            check(bool(missing.isError), "describe_table rejects an unknown name")

            grouped = await session.call_tool(
                "run_read_query",
                {"sql": "SELECT enrollment_status, COUNT(*) AS n FROM students GROUP BY enrollment_status ORDER BY enrollment_status"},
            )
            check(not grouped.isError, "run_read_query SELECT succeeded")
            grouped_data = _data(grouped)
            print(f"     status counts -> {grouped_data['rows']}")
            check(grouped_data["row_count"] == 4 and grouped_data["truncated"] is False, "four enrollment statuses")

            literal = await session.call_tool(
                "run_read_query",
                {"sql": "SELECT COUNT(*) AS n FROM departments WHERE name = 'DROP'"},
            )
            check(not literal.isError, "SELECT with the word DROP inside a string is allowed")

            cte = await session.call_tool(
                "run_read_query",
                {
                    "sql": (
                        "WITH majors AS ("
                        " SELECT major_department_id FROM students GROUP BY major_department_id"
                        ") SELECT COUNT(*) AS n FROM majors"
                    )
                },
            )
            check(not cte.isError and _data(cte)["rows"] == [[120]], "WITH ... SELECT is allowed")

            limited = await session.call_tool(
                "run_read_query",
                {"sql": "SELECT student_id FROM students"},
            )
            check(not limited.isError, "unbounded SELECT succeeded")
            limited_data = _data(limited)
            print(f"     student_id rows -> {limited_data['row_count']} truncated={limited_data['truncated']}")
            check(
                limited_data["row_count"] == 500 and limited_data["truncated"] is True,
                "row limit stops at 500 and reports truncation",
            )

            deleted = await session.call_tool("run_read_query", {"sql": "DELETE FROM students"})
            check(bool(deleted.isError), "DELETE is rejected")
            print(f"     delete -> {_text(deleted)}")

            stacked = await session.call_tool(
                "run_read_query",
                {"sql": "SELECT 1; DROP TABLE students"},
            )
            check(bool(stacked.isError), "stacked statements are rejected")
            print(f"     stacked -> {_text(stacked)}")

            slow = await session.call_tool(
                "run_read_query",
                {"sql": "SELECT COUNT(*) FROM students AS a, students AS b, students AS c, faculty"},
            )
            check(bool(slow.isError) and "timed out" in _text(slow).lower(), "long query times out")
            print(f"     timeout -> {_text(slow)}")

    if failures:
        print(f"\n{len(failures)} check(s) failed:")
        for item in failures:
            print(f"  - {item}")
        return 1
    print("\nAll tool checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
