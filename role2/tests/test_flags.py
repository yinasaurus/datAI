"""Config flags switch schema source, single-shot vs repair, and the prompts."""

from __future__ import annotations

import asyncio
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent.prompts import SQL_SYSTEM, SUMMARY_SYSTEM
from agent.loop import run_agent
from tests.fakes import FakeTools, ScriptedModel, config, query_error, query_ok


class FlagTests(unittest.TestCase):
    def test_single_shot_does_not_repair(self) -> None:
        tools = FakeTools(
            [query_error('column "revenue" does not exist'), query_ok()]
        )
        model = ScriptedModel(
            ["SELECT revenue FROM orders", "SELECT 1", "This summary must not run."]
        )
        result = asyncio.run(
            run_agent(
                "What is revenue?",
                config(mode="single_shot", max_repairs=3),
                model,
                tools,
            )
        )

        self.assertEqual(result["mode"], "single_shot")
        self.assertEqual(result["attempt_count"], 1)
        self.assertEqual(len(tools.queries), 1)
        self.assertEqual(len(model.calls), 1)
        self.assertIsNone(result["succeeded_attempt"])

    def test_schema_mode_selects_the_tool(self) -> None:
        full_tools = FakeTools([query_ok()])
        full_model = ScriptedModel(["SELECT order_id FROM orders", "One column."])
        asyncio.run(
            run_agent("List orders", config(schema_mode="full"), full_model, full_tools)
        )
        self.assertEqual(full_tools.schema_calls, [("full",)])

        rag_tools = FakeTools([query_ok()])
        rag_model = ScriptedModel(["SELECT order_id FROM orders", "One column."])
        asyncio.run(
            run_agent(
                "List orders",
                config(schema_mode="rag", schema_k=2),
                rag_model,
                rag_tools,
            )
        )
        self.assertEqual(rag_tools.schema_calls, [("rag", "List orders", 2)])
        self.assertIn("<untrusted_schema>", rag_model.calls[0][1])

    def test_schema_failure_does_not_call_the_model(self) -> None:
        tools = FakeTools([], schema_error="DATABASE_URL is not set.")
        model = ScriptedModel(["SELECT 1"])
        result = asyncio.run(run_agent("List orders", config(schema_mode="full"), model, tools))

        self.assertEqual(result["attempt_count"], 0)
        self.assertIn("DATABASE_URL", result["error"] or "")
        self.assertEqual(model.calls, [])

    def test_prompts_treat_database_text_as_data(self) -> None:
        combined = f"{SQL_SYSTEM}\n{SUMMARY_SYSTEM}".lower()
        self.assertIn("untrusted", combined)
        self.assertIn("not instructions", combined)


if __name__ == "__main__":
    unittest.main()
