"""Split schema_docs.md into one document per table or relationship."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

SCHEMA_DOCS = Path(__file__).resolve().parents[1] / "db" / "schema_docs.md"

TABLES = (
    "buildings",
    "departments",
    "classrooms",
    "terms",
    "faculty",
    "students",
    "courses",
    "course_prerequisites",
    "degree_requirements",
    "sections",
    "enrollments",
    "advisor_assignments",
)

# Useful to the agent, but not a table or a relationship.
_OVERVIEW_TITLES = {
    "Sensitive columns",
    "Campuses",
    "Conventions that affect answers",
    "Controlled values",
    "Row counts",
}

_SKIP_TITLES = {"Project layout"}


@dataclass(frozen=True)
class SchemaChunk:
    id: str
    title: str
    kind: str
    text: str

    def to_dict(self) -> dict[str, str]:
        return {"id": self.id, "title": self.title, "kind": self.kind, "text": self.text}

    @classmethod
    def from_dict(cls, raw: dict[str, str]) -> SchemaChunk:
        return cls(id=raw["id"], title=raw["title"], kind=raw["kind"], text=raw["text"])


def load_chunks(path: Path | None = None) -> list[SchemaChunk]:
    """Read the schema write-up and return embeddable documents."""
    document = (path or SCHEMA_DOCS).read_text(encoding="utf-8")
    intro, sections = _split_sections(document)
    chunks: list[SchemaChunk] = []
    intro = _opening_summary(intro)
    if intro:
        chunks.append(
            SchemaChunk(
                id="overview:snapshot",
                title="Database snapshot",
                kind="overview",
                text=_clean(
                    "Overview of the Northline State University database.\n\n" + intro
                ),
            )
        )
    for title, body in sections:
        if title in _SKIP_TITLES:
            continue
        if title in TABLES:
            chunks.append(_table_chunk(title, body))
        elif title == "How the rows fit together":
            chunks.extend(_relationship_chunks(body))
        elif title in _OVERVIEW_TITLES:
            slug = _slug(title)
            chunks.append(
                SchemaChunk(
                    id=f"overview:{slug}",
                    title=title,
                    kind="overview",
                    text=_clean(f"{title}\n\n{body}"),
                )
            )
        else:
            raise ValueError(f"Unrecognized schema section {title!r}. Add it to the chunker.")
    _check_coverage(chunks)
    return chunks


def _table_chunk(name: str, body: str) -> SchemaChunk:
    return SchemaChunk(
        id=f"table:{name}",
        title=name,
        kind="table",
        text=_clean(f"Table `{name}`\n\n{body}"),
    )


def _relationship_chunks(body: str) -> list[SchemaChunk]:
    prose, diagram = _split_fenced_block(body)
    chunks: list[SchemaChunk] = []
    for line in prose.splitlines():
        stripped = line.strip()
        if not stripped.startswith("- "):
            continue
        statement = stripped[2:].strip()
        chunks.append(
            SchemaChunk(
                id=f"relationship:{_slug(statement)}",
                title=statement,
                kind="relationship",
                text=f"Relationship: {statement}",
            )
        )
    if diagram:
        chunks.append(
            SchemaChunk(
                id="relationship:diagram",
                title="Entity relationship diagram",
                kind="relationship",
                text=_clean(
                    "Relationships between tables, as an entity diagram.\n\n" + diagram
                ),
            )
        )
    if not chunks:
        raise ValueError("The relationship section produced no chunks.")
    return chunks


def _split_sections(document: str) -> tuple[str, list[tuple[str, str]]]:
    """Return the preamble and each `## ` section as (title, body)."""
    parts = re.split(r"(?m)^## ", document)
    preamble = parts[0]
    # Drop the H1 title block's trailing '---' separator from the preamble.
    preamble = preamble.split("\n---\n", 1)[0]
    sections: list[tuple[str, str]] = []
    for part in parts[1:]:
        title, _, body = part.partition("\n")
        body = body.strip()
        if body.endswith("---"):
            body = body[: -len("---")].strip()
        sections.append((title.strip(), body))
    return preamble.strip(), sections


def _split_fenced_block(body: str) -> tuple[str, str]:
    match = re.search(r"```.*?```", body, flags=re.DOTALL)
    if not match:
        return body, ""
    prose = (body[: match.start()] + body[match.end() :]).strip()
    return prose, match.group(0).strip()


def _slug(text: str) -> str:
    words = re.findall(r"[a-z0-9]+", text.lower())
    slug = "-".join(words[:8])
    return slug or "item"


def _clean(text: str) -> str:
    return re.sub(r"\n{3,}", "\n\n", text).strip() + "\n"


def _opening_summary(preamble: str) -> str:
    """Keep the snapshot description and drop rebuild instructions."""
    kept: list[str] = []
    for paragraph in re.split(r"\n\s*\n", _drop_fences(preamble)):
        paragraph = paragraph.strip()
        if not paragraph or paragraph.startswith("Rebuild"):
            break
        kept.append(paragraph)
    return "\n\n".join(kept)


def _drop_fences(text: str) -> str:
    return re.sub(r"```.*?```", "", text, flags=re.DOTALL)


def _check_coverage(chunks: list[SchemaChunk]) -> None:
    found = {chunk.title for chunk in chunks if chunk.kind == "table"}
    missing = [name for name in TABLES if name not in found]
    if missing:
        raise ValueError(f"Schema chunks are missing tables: {', '.join(missing)}")
    if not any(chunk.kind == "relationship" for chunk in chunks):
        raise ValueError("Schema chunks include no relationships.")
    ids = [chunk.id for chunk in chunks]
    if len(ids) != len(set(ids)):
        raise ValueError("Schema chunk ids are not unique.")
