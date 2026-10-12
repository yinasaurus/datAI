"""Turn schema_docs.yaml into retrievable chunks and into the full-schema file.

    python -m schema_rag.docs     # (re)writes data/full_schema.md

Both RQ1 conditions read the same text: the full-schema baseline gets every
chunk joined together, and Schema RAG gets only the top-k chunks. So any
difference between them comes from retrieval, not from different wording.
"""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from interfaces.types import SchemaChunk

DOCS_PATH = ROOT / "schema_rag" / "schema_docs.yaml"
FULL_SCHEMA_PATH = ROOT / "data" / "full_schema.md"


def load_docs(path: Path = DOCS_PATH) -> dict:
    with path.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def docs_fingerprint(path: Path = DOCS_PATH) -> str:
    """Changes whenever the YAML changes, so a stale index gets rebuilt."""
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


def table_text(name: str, table: dict) -> str:
    lines = [f"Table {name}: {table['description'].strip()}", "Columns:"]
    lines += [f"- {column}: {text}" for column, text in table["columns"].items()]
    if table.get("joins"):
        lines.append("Joins:")
        lines += [f"- {join}" for join in table["joins"]]
    return "\n".join(lines)


def example_text(example: dict) -> str:
    return (
        f"Example question: {example['question']}\n"
        f"Tables: {', '.join(example['tables'])}\n"
        f"SQL:\n{example['sql'].strip()}"
    )


def build_chunks(docs: dict | None = None) -> list[SchemaChunk]:
    """One chunk per table, then one per worked example."""
    docs = docs if docs is not None else load_docs()
    chunks = [
        SchemaChunk(id=f"table:{name}", source=name, text=table_text(name, table))
        for name, table in docs["tables"].items()
    ]
    chunks += [
        SchemaChunk(id=f"example:{index}", source=",".join(example["tables"]), text=example_text(example))
        for index, example in enumerate(docs.get("examples", []), start=1)
    ]
    return chunks


def render_full_schema(docs: dict | None = None) -> str:
    chunks = build_chunks(docs)
    header = (
        "# Olist marketplace database schema\n\n"
        "PostgreSQL. Generated from schema_rag/schema_docs.yaml by `python -m schema_rag.docs`. "
        "Do not edit by hand.\n"
    )
    return header + "\n" + "\n\n".join(chunk.text for chunk in chunks) + "\n"


def main() -> int:
    FULL_SCHEMA_PATH.parent.mkdir(parents=True, exist_ok=True)
    FULL_SCHEMA_PATH.write_text(render_full_schema(), encoding="utf-8")
    print(f"Wrote {FULL_SCHEMA_PATH.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
