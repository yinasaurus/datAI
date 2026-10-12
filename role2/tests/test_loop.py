"""Repair loop: retry on a SQL error, stop at the attempt limit, accept zero rows."""

from __future__ import annotations

import asyncio
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent.loop import run_agent
from tests.fakes import FakeTools, ScriptedModel, config, query_error, query_ok


class RepairLoopTests(unittest.TestCase):
    def test_retries_and_stops_at_three(self) -> None:
        error = 'column "revenue" does not exist'
        tools = FakeTools([query_error(error), query_error(error), query_error(error), query_ok()])
        model = ScriptedModel(
            [
                "SELECT revenue FROM orders",
                "SELECT revenue FROM orders",
                "SELECT revenue FROM orders",
                "This summary must not be requested.",
            ]
        )
        result = asyncio.run(
            run_agent("What is revenue?", config(max_repairs=3), model, tools)
        )

        self.assertEqual(result["attempt_count"], 3)
        self.assertIsNone(result["succeeded_attempt"])
        self.assertEqual(len(tools.queries), 3)
        self.assertEqual(len(model.calls), 3)
        self.assertIn(error, result["error"] or "")
        self.assertIn(error, model.calls[1][1])
        self.assertIn(error, model.calls[2][1])

    def test_second_attempt_can_succeed(self) -> None:
        tools = FakeTools(
            [query_error('column "revenue" does not exist'), query_ok([["delivered", 2]])]
        )
        model = ScriptedModel(
            [
                "SELECT revenue FROM orders",
                "SELECT status, COUNT(*) AS n FROM orders GROUP BY status",
                "Two orders are delivered.",
            ]
        )
        with tempfile.TemporaryDirectory() as folder:
            log_path = Path(folder) / "runs.jsonl"
            result = asyncio.run(
                run_agent("How many delivered orders?", config(), model, tools, log_path=log_path)
            )
            logged = log_path.read_text(encoding="utf-8").strip().splitlines()

        self.assertEqual(result["succeeded_attempt"], 2)
        self.assertEqual(result["attempt_count"], 2)
        self.assertEqual(result["row_count"], 1)
        self.assertIsNone(result["error"])
        self.assertIn("SQL:", result["answer"])
        self.assertIn("Row count: 1", result["answer"])
        self.assertEqual(len(logged), 1)
        self.assertEqual(result["tokens"]["total"], 14 * 3)
        self.assertEqual(len(result["calls"]), 3)
        self.assertEqual(result["calls"][0]["step"], "write_sql")
        self.assertEqual(result["calls"][2]["step"], "summarize")

    def test_zero_rows_is_success_and_does_not_repair(self) -> None:
        tools = FakeTools([query_ok([])])
        model = ScriptedModel(["SELECT status FROM orders WHERE status = 'missing'", "None match."])
        result = asyncio.run(run_agent("Any missing orders?", config(), model, tools))

        self.assertEqual(result["attempt_count"], 1)
        self.assertEqual(result["succeeded_attempt"], 1)
        self.assertEqual(result["row_count"], 0)
        self.assertEqual(len(model.calls), 2)


if __name__ == "__main__":
    unittest.main()
