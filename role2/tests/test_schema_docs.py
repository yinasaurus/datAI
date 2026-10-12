"""Role 1: the schema docs match the SQL, and retrieval ranks and caches correctly.

No database and no embedding model: a word-overlap embedder stands in for bge.
"""

from __future__ import annotations

import re
import sys
import tempfile
import unittest
import zlib
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from schema_rag.docs import build_chunks, load_docs, render_full_schema
from schema_rag.index import SchemaIndex, load_index

SCHEMA_SQL = ROOT / "db" / "init" / "01_schema.sql"


def sql_tables() -> dict[str, list[str]]:
    """Table -> column names, read from the CREATE TABLE statements."""
    tables: dict[str, list[str]] = {}
    for name, body in re.findall(r"CREATE TABLE (\w+) \((.*?)\n\);", SCHEMA_SQL.read_text(), re.S):
        columns = []
        for line in body.splitlines():
            match = re.match(r"\s+(\w+) ", line)
            if match and match.group(1) not in ("PRIMARY", "FOREIGN"):
                columns.append(match.group(1))
        tables[name] = columns
    return tables


def word_embedder(texts):
    """Hash each word into one of 512 buckets. Shared words make vectors similar."""
    vectors = np.zeros((len(texts), 512), dtype=np.float32)
    for row, text in enumerate(texts):
        for word in re.findall(r"[a-z_]+", text.lower()):
            for part in {word, *word.split("_")}:
                vectors[row, zlib.crc32(part.encode()) % 512] += 1.0
    return vectors


class SchemaDocsTests(unittest.TestCase):
    def test_docs_cover_every_table_and_column_in_the_sql(self) -> None:
        docs = load_docs()["tables"]
        tables = sql_tables()
        self.assertEqual(len(tables), 13)
        self.assertEqual(set(docs), set(tables))
        for name, columns in tables.items():
            self.assertEqual(list(docs[name]["columns"]), columns, name)

    def test_example_queries_name_real_tables(self) -> None:
        tables = set(sql_tables())
        for example in load_docs()["examples"]:
            self.assertLessEqual(set(example["tables"]), tables, example["question"])

    def test_one_chunk_per_table_and_example(self) -> None:
        docs = load_docs()
        chunks = build_chunks(docs)
        self.assertEqual(len(chunks), len(docs["tables"]) + len(docs["examples"]))
        self.assertEqual(len({chunk.id for chunk in chunks}), len(chunks))

    def test_full_schema_contains_every_chunk(self) -> None:
        text = render_full_schema()
        for chunk in build_chunks():
            self.assertIn(chunk.text, text)


class RetrievalTests(unittest.TestCase):
    def test_search_ranks_the_matching_table_first(self) -> None:
        index = SchemaIndex.build(build_chunks(), word_embedder)
        top = index.search("Which bank_name and account_manager_id does each seller payout account have?", 1)
        self.assertEqual(top[0][0].id, "table:seller_payout_accounts")

    def test_search_returns_k_chunks_best_first(self) -> None:
        index = SchemaIndex.build(build_chunks(), word_embedder)
        results = index.search("average review_score", 3)
        self.assertEqual(len(results), 3)
        scores = [score for _chunk, score in results]
        self.assertEqual(scores, sorted(scores, reverse=True))

    def test_index_is_cached_until_the_docs_change(self) -> None:
        calls = []

        def counting(texts):
            calls.append(len(texts))
            return word_embedder(texts)

        with tempfile.TemporaryDirectory() as folder:
            load_index(counting, Path(folder))
            load_index(counting, Path(folder))
            # The first load embeds every chunk. The second embeds nothing.
            self.assertEqual(calls, [len(build_chunks())])


if __name__ == "__main__":
    unittest.main()
