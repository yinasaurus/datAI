# Role 2 — Agent and MCP

This folder is the Agent and MCP part of the IS469 analytics project (Olist marketplace, PostgreSQL, Gemini). The Northline practice code at the repository root is a separate exercise and is not used here.

Non-technical staff ask a question in English. This role gets schema context, asks Gemini for one SQL statement, runs it through an MCP tool, and on a database error lets the model try again. The reply includes the SQL and the row count.

## What I would say in the presentation

The model never opens the database. It can only call three tools on an MCP server:

| Tool | When it is used |
| --- | --- |
| `retrieve_schema(question, k)` | RAG condition. Asks Role 1's retriever for a few schema chunks. |
| `get_full_schema()` | No-RAG baseline. Puts the whole schema in the prompt. |
| `run_read_query(sql)` | The only tool that executes SQL. |

Those stay as three tools because RQ1 switches the schema source without changing execution. The guardrail switch is **not** a fourth argument on the tool. It is an environment flag on the server process, so a prompt cannot turn the checks off.

`run_read_query` calls Role 3's `check_sql` first when `guardrails=on`. If the hook says no, the database is not contacted and the reason is returned as text. If the database itself errors, that message is returned the same way. The agent reads it and writes a new SELECT. A query that returns zero rows is a success, not a reason to repair.

`mode=single_shot` is the RQ2 baseline: the same model, the same tools, one SQL attempt, no repair. `mode=agent_loop` may try up to `max_repairs` times, including the first try. The default is 3.

Schema text, review text, and cell values are wrapped as untrusted data in the prompt. The system prompt says they are data, not instructions.

## Contracts for teammates

Role 1 replaces `interfaces/retriever.py`:

```python
retrieve(question: str, k: int) -> list[SchemaChunk]
```

This is now implemented in `schema_rag/` (see `schema_rag/README.md`). `role2/data/full_schema.md` feeds the no-RAG baseline; it is generated from the same schema docs as the RAG chunks.

Role 3 replaces `interfaces/guardrails.py`:

```python
check_sql(sql: str) -> GuardrailDecision  # allowed: bool, reason: str
```

The stub allows everything. A block must include a short `reason`, because that string is what the agent sees.

Role 4 calls:

```python
answer_question(question: str, config: dict | None) -> dict
```

The dict contains `answer`, `sql`, `row_count`, `attempts`, `attempt_count`, `succeeded_attempt`, `latency_ms`, `tokens`, `calls`, and `error`. `error` is `None` when a query succeeded. Each item in `calls` is one Gemini request with its own latency and token counts. `tokens` is the sum. One JSON line per question is appended to the log.

`config` keys:

| Flag | Values | Effect |
| --- | --- | --- |
| `schema_mode` | `full` or `rag` | Full schema in the prompt, or top-k chunks |
| `mode` | `single_shot` or `agent_loop` | One SQL attempt, or repair up to `max_repairs` |
| `max_repairs` | integer, default `3` | SQL attempts in the agent loop, including the first |
| `guardrails` | `on` or `off` | Call `check_sql`, or skip it |
| `temperature` | default `0` | Sent to Gemini |
| `seed` | default `42` | Sent to Gemini |
| `schema_k` | default `4` | Chunks requested in RAG mode |

## Setup

From `role2/`, with the repository virtual environment or a new one:

```text
pip install -r requirements.txt
copy .env.example .env
```

Put the Gemini key in `.env`. Set `GEMINI_MODEL` there too. The Python code reads that variable and does not name a model itself. The example value is `gemini-3.8-flash`.

Start the database (PostgreSQL 16) and load the data:

```text
docker compose up -d
python db/load_olist.py --download
python db/generate_synthetic.py
```

`DATABASE_URL` in `.env.example` already points at it. `db/init/01_schema.sql` creates the 9 Olist tables and the 4 synthetic tables the first time the container starts. If you started the old two-table sample before, run `docker compose down -v` first so the new schema is created. `--download` fetches the Olist CSVs into `data/raw/` from Olist's own GitHub, so no Kaggle login is needed.

## Run the MCP server

The agent starts the server itself. To run it by hand:

```text
python mcp_server/server.py
```

That process speaks MCP over stdin and stdout. It is not an HTTP port.

## Run one question

```text
python agent/run.py "How many orders are delivered?"
```

The answer, the SQL, the attempt that succeeded, the token total, and the latency are printed. The same record is appended to `logs/runs.jsonl`.

Role 4 does not need the command line:

```python
from agent.answer import answer_question

answer_question(
    "How many orders are delivered?",
    {"schema_mode": "rag", "mode": "agent_loop", "max_repairs": 3, "guardrails": "on"},
)
```

## Tests

No API key and no database:

```text
python -m unittest discover -s tests
```

They check that a SQL error is retried and that the loop stops at 3, that a zero-row result is not treated as a failure, that `single_shot` does not repair, that `schema_mode` picks the matching tool, and that `guardrails=off` does not call the hook.

## Files, in the order I would explain them

| File | What it does |
| --- | --- |
| `interfaces/types.py` | The shared shapes: a schema chunk, a guardrail decision, the run flags, and the answer dict |
| `interfaces/retriever.py` | Role 1's function. Ranks schema chunks with `schema_rag/` |
| `interfaces/guardrails.py` | Role 3's function. Stub allows every statement |
| `mcp_server/db.py` | Opens PostgreSQL and turns a failure into one readable sentence |
| `mcp_server/tools.py` | The three tools. This is where the guardrail flag is applied |
| `mcp_server/server.py` | Publishes those functions over MCP. Reads `GUARDRAILS` from the environment |
| `agent/prompts.py` | Tells Gemini to write one SELECT, and that schema and rows are data only |
| `agent/llm.py` | Calls Gemini using `GEMINI_MODEL`, and records tokens and latency |
| `agent/sql_text.py` | Pulls the SELECT out of the model's reply |
| `agent/loop.py` | Gets schema, writes SQL, runs it, repairs, then summarizes |
| `agent/mcp_client.py` | Starts the MCP server and calls the three tools |
| `agent/runlog.py` | Appends one JSON line per question |
| `agent/answer.py` | `answer_question`, the function Role 4 calls |
| `agent/config.py` | Reads the flags from `.env` and lets a dict override them |
| `agent/run.py` | Command-line wrapper around `answer_question` |
| `docker-compose.yml` | PostgreSQL 16 for a test before the real data exists |
| `db/init/01_schema.sql` | Role 1. 9 Olist tables plus 4 synthetic tables, keys and indexes |
| `db/load_olist.py` | Role 1. Loads and cleans the Olist CSVs |
| `db/generate_synthetic.py` | Role 1. Fills the synthetic tables with fake data (seed 42) |
| `schema_rag/` | Role 1. Schema docs, embedding index, retriever and recall@k check |
