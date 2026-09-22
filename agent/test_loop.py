"""Exercise the agent loop against the real RAG index and MCP server.

The language model is scripted so the retry path does not need an API key.
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent.llm import extract_sql
from agent.loop import ask

GOOD_SQL = (
    "SELECT enrollment_status, COUNT(*) AS n "
    "FROM students GROUP BY enrollment_status ORDER BY enrollment_status"
)
BAD_SQL = "SELECT status, COUNT(*) AS n FROM students GROUP BY status"
SUMMARY = "There are 611 active, 91 graduated, 46 on leave, and 52 withdrawn."


class ScriptedModel:
    def __init__(self, replies: list[str]) -> None:
        self._replies = list(replies)
        self.calls: list[tuple[str, str]] = []

    def complete(self, *, system: str, user: str) -> str:
        self.calls.append((system, user))
        if not self._replies:
            raise RuntimeError("Scripted model ran out of replies.")
        return self._replies.pop(0)


def check(condition: bool, label: str, failures: list[str]) -> None:
    print(f"{'ok  ' if condition else 'FAIL'} {label}")
    if not condition:
        failures.append(label)


def main() -> int:
    failures: list[str] = []
    check(
        extract_sql("```sql\nSELECT 1;\n```") == "SELECT 1",
        "extract_sql reads a fenced statement",
        failures,
    )
    check(extract_sql("Here you go:\nSELECT 1 AS n") == "SELECT 1 AS n", "extract_sql finds a bare SELECT", failures)

    with tempfile.TemporaryDirectory() as temp:
        log_path = Path(temp) / "runs.jsonl"

        first = ScriptedModel([GOOD_SQL, SUMMARY])
        run = ask("How many students are in each enrollment status?", model=first, log_path=log_path)
        check(run.success and run.attempt_count == 1, "first query succeeds on attempt 1", failures)
        check(run.final_answer == SUMMARY, "summary is the model reply", failures)
        check(run.sql == GOOD_SQL, "logged SQL is the successful statement", failures)
        check(any(item["id"].startswith("table:") for item in run.retrieved_schema), "schema chunks were retrieved", failures)
        print(f"     answer: {run.final_answer}")

        retry = ScriptedModel([BAD_SQL, GOOD_SQL, SUMMARY])
        run = ask("Break down students by enrollment status.", model=retry, log_path=log_path)
        check(run.success and run.attempt_count == 2, "bad column is retried and then succeeds", failures)
        check(run.attempts[0].error is not None and run.attempts[1].error is None, "first attempt stores the error", failures)
        check("no such column" in (run.attempts[0].error or "").lower(), "error names the missing column", failures)
        check(BAD_SQL in retry.calls[1][1] and "no such column" in retry.calls[1][1].lower(), "error is fed back into the next prompt", failures)
        print(f"     retry error: {run.attempts[0].error}")

        stuck = ScriptedModel(["DELETE FROM students"] * 3 + [SUMMARY])
        run = ask("Remove every student.", model=stuck, log_path=log_path)
        check(not run.success and run.attempt_count == 3, "writes stop after 3 attempts", failures)
        check(len(stuck.calls) == 3, "a failed run does not call the summarizer", failures)
        check(all(item.error for item in run.attempts), "each rejected attempt keeps its error", failures)

        records = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()]
        required = {"question", "retrieved_schema", "attempts", "attempt_count", "sql", "final_answer", "success"}
        check(len(records) == 3 and required <= set(records[1]), "JSONL log has the evaluation fields", failures)
        check(records[1]["attempt_count"] == 2 and records[1]["attempts"][0]["sql"] == BAD_SQL, "log stores each generated statement", failures)

    if failures:
        print(f"\n{len(failures)} check(s) failed.")
        return 1
    print("\nAgent loop checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
