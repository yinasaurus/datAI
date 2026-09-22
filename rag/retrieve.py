"""Embed schema chunks and retrieve the closest ones with FAISS.

Embeddings are local. The model is BAAI/bge-small-en-v1.5, a small English
retrieval model run by ONNX through fastembed. No API key is required.
Vectors are L2-normalized and searched with inner product, which is cosine
similarity.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import faiss
import numpy as np
from fastembed import TextEmbedding

from rag.chunk import SchemaChunk, load_chunks

MODEL_NAME = "BAAI/bge-small-en-v1.5"
INDEX_DIR = Path(__file__).resolve().parent / "index"
INDEX_PATH = INDEX_DIR / "schema.faiss"
CHUNKS_PATH = INDEX_DIR / "chunks.json"

_model: TextEmbedding | None = None


@dataclass(frozen=True)
class RetrievedChunk:
    id: str
    title: str
    kind: str
    score: float
    text: str


def build_index(force: bool = False) -> list[SchemaChunk]:
    """Embed every schema chunk and write the FAISS index next to this package."""
    chunks = load_chunks()
    if not force and _index_matches(chunks):
        return chunks
    vectors = _embed_passages([chunk.text for chunk in chunks])
    index = faiss.IndexFlatIP(vectors.shape[1])
    index.add(vectors)
    INDEX_DIR.mkdir(parents=True, exist_ok=True)
    faiss.write_index(index, str(INDEX_PATH))
    payload = {
        "model": MODEL_NAME,
        "chunks": [chunk.to_dict() for chunk in chunks],
    }
    CHUNKS_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return chunks


def retrieve(question: str, k: int = 3) -> list[RetrievedChunk]:
    """Return the top-k schema chunks for a natural-language question."""
    if not question or not question.strip():
        raise ValueError("Question is empty.")
    if k < 1:
        raise ValueError("k must be at least 1.")
    chunks = _load_chunks()
    index = faiss.read_index(str(INDEX_PATH))
    if index.ntotal != len(chunks):
        chunks = build_index(force=True)
        index = faiss.read_index(str(INDEX_PATH))
    k = min(k, len(chunks))
    query = _embed_query(question.strip())
    scores, ids = index.search(query, k)
    hits: list[RetrievedChunk] = []
    for score, row_id in zip(scores[0], ids[0], strict=True):
        if row_id < 0:
            continue
        chunk = chunks[int(row_id)]
        hits.append(
            RetrievedChunk(
                id=chunk.id,
                title=chunk.title,
                kind=chunk.kind,
                score=float(score),
                text=chunk.text,
            )
        )
    return hits


def _index_matches(chunks: list[SchemaChunk]) -> bool:
    if not INDEX_PATH.is_file() or not CHUNKS_PATH.is_file():
        return False
    stored = json.loads(CHUNKS_PATH.read_text(encoding="utf-8"))
    if stored.get("model") != MODEL_NAME:
        return False
    stored_chunks = stored.get("chunks", [])
    return [item["id"] for item in stored_chunks] == [chunk.id for chunk in chunks] and [
        item["text"] for item in stored_chunks
    ] == [chunk.text for chunk in chunks]


def _load_chunks() -> list[SchemaChunk]:
    if not INDEX_PATH.is_file() or not CHUNKS_PATH.is_file():
        build_index()
    stored = json.loads(CHUNKS_PATH.read_text(encoding="utf-8"))
    if stored.get("model") != MODEL_NAME:
        build_index(force=True)
        stored = json.loads(CHUNKS_PATH.read_text(encoding="utf-8"))
    return [SchemaChunk.from_dict(item) for item in stored["chunks"]]


def _embedding_model() -> TextEmbedding:
    global _model
    if _model is None:
        # Keep the ONNX model out of the temp directory so it survives a reboot.
        cache = Path.home() / ".cache" / "fastembed"
        cache.mkdir(parents=True, exist_ok=True)
        _model = TextEmbedding(model_name=MODEL_NAME, cache_dir=str(cache))
    return _model


def _embed_passages(texts: list[str]) -> np.ndarray:
    vectors = np.vstack(list(_embedding_model().embed(texts))).astype("float32")
    faiss.normalize_L2(vectors)
    return vectors


def _embed_query(question: str) -> np.ndarray:
    model = _embedding_model()
    embed = getattr(model, "query_embed", None)
    source = embed([question]) if embed is not None else model.embed([question])
    vector = np.vstack(list(source)).astype("float32")
    faiss.normalize_L2(vector)
    return vector
