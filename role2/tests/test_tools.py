"""The guardrail flag is server config: on calls the hook, off skips it."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from interfaces.types import GuardrailDecision
from mcp_server.tools import execute_sql, retrieve_schema


class ToolTests(unittest.TestCase):
    def test_guardrails_on_blocks_before_the_database(self) -> None:
        def deny(sql: str) -> GuardrailDecision:
            del sql
            return GuardrailDecision(False, "Only SELECT statements are allowed.")

        def explode(sql: str):
            raise AssertionError(f"database should not be called for {sql}")

        result = execute_sql("DELETE FROM orders", guardrails="on", check=deny, query=explode)
        self.assertFalse(result["ok"])
        self.assertIn("Only SELECT", result["error"] or "")
        self.assertEqual(result["row_count"], 0)

    def test_guardrails_off_skips_the_hook(self) -> None:
        def deny(sql: str) -> GuardrailDecision:
            raise AssertionError(f"hook should not run when guardrails are off: {sql}")

        def query(sql: str):
            self.assertEqual(sql, "SELECT order_id FROM orders")
            return ["order_id"], [[1], [2]]

        result = execute_sql(
            "SELECT order_id FROM orders",
            guardrails="off",
            check=deny,
            query=query,
        )
        self.assertTrue(result["ok"])
        self.assertEqual(result["row_count"], 2)
        self.assertIsNone(result["error"])

    def test_database_error_is_readable_text(self) -> None:
        def query(sql: str):
            from mcp_server.db import DatabaseError

            raise DatabaseError('column "revenue" does not exist')

        result = execute_sql("SELECT revenue FROM orders", guardrails="off", query=query)
        self.assertFalse(result["ok"])
        self.assertIn("revenue", result["error"] or "")

    def test_retrieve_schema_uses_the_stub(self) -> None:
        payload = retrieve_schema("How many orders are delivered?", k=2)
        self.assertEqual(payload["error"], "")
        chunks = payload["chunks"]
        self.assertIsInstance(chunks, list)
        self.assertEqual(len(chunks), 2)
        self.assertIn("orders", str(payload["text"]))


if __name__ == "__main__":
    unittest.main()
