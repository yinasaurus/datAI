"""Build the schema index if needed and show retrieval for five questions.

Run from the project root:

    python rag/test_retrieve.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from rag.chunk import load_chunks
from rag.retrieve import build_index, retrieve

# Each question should surface a specific table inside the top 3 chunks.
QUESTIONS = [
    (
        "Who is teaching Introduction to Programming at Riverton in Fall 2026?",
        "table:sections",
    ),
    (
        "What is the average faculty salary by academic rank?",
        "table:faculty",
    ),
    (
        "Which general-education courses does a Nursing major have to take?",
        "table:degree_requirements",
    ),
    (
        "How many active students are majoring in Nursing at Westfield?",
        "table:students",
    ),
    (
        "What are the prerequisites for Operating Systems?",
        "table:course_prerequisites",
    ),
]


def main() -> int:
    chunks = load_chunks()
    print(f"Chunked schema_docs.md into {len(chunks)} documents:")
    for chunk in chunks:
        print(f"  {chunk.kind:<14} {chunk.id}")
    print()
    build_index()

    failures: list[str] = []
    for question, expected in QUESTIONS:
        hits = retrieve(question, k=3)
        print(question)
        for rank, hit in enumerate(hits, start=1):
            preview = " ".join(hit.text.split())
            if len(preview) > 110:
                preview = preview[:107] + "..."
            print(f"  {rank}. {hit.score:.3f}  {hit.id}")
            print(f"     {preview}")
        found = [hit.id for hit in hits]
        ok = expected in found
        print(f"     expected {expected}: {'found' if ok else 'MISSING'}")
        print()
        if not ok:
            failures.append(f"{expected} not in top 3 for: {question}")

    if failures:
        print(f"{len(failures)} question(s) missed the expected chunk.")
        return 1
    print("All five questions retrieved the expected schema chunk.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
