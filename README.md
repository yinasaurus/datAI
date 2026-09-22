# Northline SQL assistant

A local assistant that answers questions about a fictional university by writing SQL. The database is SQLite. The model never opens the file itself. It retrieves schema notes, writes a `SELECT`, and runs that statement through a read-only tool server.

The school is Northline State University. The data is a snapshot of **22 September 2026** (Fall 2026), not "today" on the clock. All people, SSNs, and salaries are synthetic.

## How a question is answered

1. **Schema search** (`rag/`). `db/schema_docs.md` is split into short passages, embedded locally, and stored in a FAISS index. A question returns the few passages most likely to name the right tables.
2. **SQL** (`agent/`). A chat model writes one SQLite `SELECT` from those passages. `WITH ... SELECT` is allowed.
3. **Execute** (`mcp_server/`). The statement is sent to an MCP server. The server does not trust the text. It runs the query only after the guardrails accept it.
4. **Retry.** If the database rejects the statement, the error goes back to the model. It may try again, up to 3 times.
5. **Answer.** On success, the model summarizes the rows in plain language. Every step is appended to `agent/logs/runs.jsonl` for a later evaluation set.

## Guardrails

Enforced in `guardrails/` on every query:

- **Read-only.** `DROP`, `DELETE`, `UPDATE`, `INSERT`, `ALTER`, and stacked statements are rejected. The connection is also opened `mode=ro`.
- **Allow-lists.** Only tables, the `current_term` view, and columns declared in `db/schema.sql` can be read.
- **Blocked columns.** `students.ssn` and `faculty.salary` cannot be selected, including via `SELECT *` or an alias. `describe_table` hides them.
- **Limits.** At most 500 rows. A query is cancelled after 5 seconds.
- **Untrusted cells.** Text that comes back from a row is data, not instructions. Phrases that try to override the prompt are redacted before the model sees them.

## Layout

| Path | What it is |
| --- | --- |
| `db/schema.sql` | 12 tables plus the `current_term` view |
| `db/seed_data.py` | Builds `db/university.db` (seed 42, about 100–1000 rows per table) |
| `db/schema_docs.md` | Human-readable schema used by search |
| `mcp_server/` | MCP tools: `list_tables`, `describe_table`, `run_read_query` |
| `rag/` | Chunk, embed, and retrieve schema passages |
| `agent/` | Question loop, prompts, and the command-line runner |
| `guardrails/` | Policy, authorizer, and injection filter |
| `eval/` | Reserved for the question evaluation set. Not built yet |

`db/university.db`, `rag/index/`, and `agent/logs/` are generated and gitignored.

## Setup

From the project root, with Python 3.11+:

```text
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe db\seed_data.py
```

On macOS or Linux, use `.venv/bin/python` instead of `.venv\Scripts\python.exe`.

A live question needs an OpenAI-compatible API key:

```text
set OPENAI_API_KEY=your-key
```

Optional: `OPENAI_MODEL` (default `gpt-4o-mini`) and `OPENAI_BASE_URL`.

## Run

```text
.venv\Scripts\python.exe agent\run.py "How many active students are there?"
```

The first schema search downloads a small local embedding model into your user cache. Later runs reuse it.

## Tests

No API key is required. The agent test uses a scripted model.

```text
.venv\Scripts\python.exe mcp_server\test_client.py
.venv\Scripts\python.exe rag\test_retrieve.py
.venv\Scripts\python.exe agent\test_loop.py
.venv\Scripts\python.exe guardrails\test_guardrails.py
```

The guardrail suite tries destructive SQL, requests for `ssn` and `salary`, and a prompt-injection string planted in a result cell.
