"""Embed the schema chunks and rank them against a question.

The embeddings are cached in schema_rag/index/ (gitignored). The cache is
rebuilt automatically when schema_docs.yaml or the model changes, or by hand:

    python -m schema_rag.index

The model is BAAI/bge-small-en-v1.5 through fastembed. It runs locally on the
CPU, and the first run downloads it (about 70 MB) into your user cache.
"""

from __future__ import annotations

import json
import os
import sys
from collections.abc import Callable, Sequence
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from interfaces.types import SchemaChunk
from schema_rag.docs import build_chunks, docs_fingerprint

INDEX_DIR = ROOT / "schema_rag" / "index"
DEFAULT_MODEL = "BAAI/bge-small-en-v1.5"
# bge models expect this prefix on queries, not on the passages.
QUERY_PREFIX = "Represent this sentence for searching relevant passages: "

Embedder = Callable[[Sequence[str]], np.ndarray]


def model_name() -> str:
    return os.environ.get("EMBEDDING_MODEL", "").strip() or DEFAULT_MODEL


def fastembed_embedder(name: str) -> Embedder:
    from fastembed import TextEmbedding

    model = TextEmbedding(model_name=name)

    def embed(texts: Sequence[str]) -> np.ndarray:
        return np.array(list(model.embed(list(texts))), dtype=np.float32)

    return embed


def _normalise(vectors: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    return vectors / np.maximum(norms, 1e-12)


class SchemaIndex:
    """Chunks plus their unit-length embeddings. Cosine similarity is a dot product."""

    def __init__(self, chunks: list[SchemaChunk], vectors: np.ndarray, embed: Embedder) -> None:
        self.chunks = chunks
        self.vectors = _normalise(vectors)
        self._embed = embed

    @classmethod
    def build(cls, chunks: list[SchemaChunk], embed: Embedder) -> "SchemaIndex":
        return cls(chunks, embed([chunk.text for chunk in chunks]), embed)

    def search(self, question: str, k: int) -> list[tuple[SchemaChunk, float]]:
        query = _normalise(self._embed([QUERY_PREFIX + question]))[0]
        scores = self.vectors @ query
        order = np.argsort(-scores, kind="stable")[:k]
        return [(self.chunks[i], float(scores[i])) for i in order]


def load_index(embed: Embedder | None = None, index_dir: Path = INDEX_DIR) -> SchemaIndex:
    """Load the cached index, or build and save it if the docs or model changed."""
    name = model_name()
    embed = embed or fastembed_embedder(name)
    chunks = build_chunks()
    meta = {"model": name, "docs": docs_fingerprint(), "ids": [chunk.id for chunk in chunks]}

    meta_path = index_dir / "meta.json"
    vectors_path = index_dir / "vectors.npy"
    if meta_path.is_file() and vectors_path.is_file():
        if json.loads(meta_path.read_text(encoding="utf-8")) == meta:
            return SchemaIndex(chunks, np.load(vectors_path), embed)

    index = SchemaIndex.build(chunks, embed)
    index_dir.mkdir(parents=True, exist_ok=True)
    np.save(vectors_path, index.vectors)
    meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return index


def main() -> int:
    index = load_index()
    print(f"Indexed {len(index.chunks)} chunks with {model_name()} into {INDEX_DIR.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
