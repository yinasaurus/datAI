"""Schema retrieval interface, implemented by Role 1 (Data and Schema RAG).

``retrieve(question, k)`` returns the passages the RAG condition puts in the prompt.
``load_authored_schema()`` returns the full schema write-up for the no-RAG baseline.

Both come from schema_rag/schema_docs.yaml, so the two conditions see the same
wording. See schema_rag/ for how chunks are built and embedded.
"""

from __future__ import annotations

from pathlib import Path

from interfaces.types import SchemaChunk

_ROOT = Path(__file__).resolve().parents[1]
_AUTHORED_SCHEMA = _ROOT / "data" / "full_schema.md"

_index = None


def retrieve(question: str, k: int = 4) -> list[SchemaChunk]:
    """Return the ``k`` schema chunks most similar to ``question``.

    Chunks are one per table (description, columns, join conditions) and one
    per worked example query. The chunk ``text`` is plain data, not instructions.
    The embedding index loads on the first call and is reused after that.
    """
    if k < 1:
        raise ValueError("k must be at least 1.")
    global _index
    if _index is None:
        from schema_rag.index import load_index

        _index = load_index()
    return [chunk for chunk, _score in _index.search(question, k)]


def load_authored_schema() -> str | None:
    """Return the full schema document, or None if it has not been generated.

    ``python -m schema_rag.docs`` writes ``role2/data/full_schema.md``.
    """
    if not _AUTHORED_SCHEMA.is_file():
        return None
    text = _AUTHORED_SCHEMA.read_text(encoding="utf-8").strip()
    return text or None
