# Schema RAG (Role 1)

The agent never sees the whole database. For each question it gets a few
pieces of schema documentation, chosen by meaning, not by keyword.

## How it works

1. **Docs.** `schema_docs.yaml` describes all 13 tables: what a row is, every
   column, and how the table joins to others. It also has 6 worked example
   queries. This is the only place schema wording lives.
2. **Chunks.** `docs.py` turns the YAML into 19 chunks: one per table (its
   description, columns and join conditions together) and one per example.
   A table chunk carries its joins, so retrieving one table also tells the
   model how to reach its neighbours.
3. **Embeddings.** `index.py` embeds each chunk with `BAAI/bge-small-en-v1.5`
   (a small local model via fastembed, no API key) and caches the vectors in
   `index/`. The cache is rebuilt when the YAML or the model changes.
4. **Retrieval.** `interfaces/retriever.py` embeds the question and returns
   the `k` chunks with the highest cosine similarity.
5. **Baseline.** `python -m schema_rag.docs` writes every chunk into
   `data/full_schema.md`, which the no-RAG condition puts in the prompt. Both
   conditions use identical wording, so RQ1 measures retrieval and nothing else.

## Commands

From `role2/`:

```text
python -m schema_rag.docs      # regenerate data/full_schema.md after editing the YAML
python -m schema_rag.index     # build the embedding cache (downloads the model once)
python -m schema_rag.recall    # recall@1..8 on 16 hand-labelled questions
python -m schema_rag.recall --k 4   # per-question detail, with missed tables
```

## Recall@k

For a question that needs tables {orders, customers}, recall@4 is 1.0 if both
appear in the top 4 chunks and 0.5 if only one does. An example chunk counts
for every table it uses. The known weak spot is bridge tables: a question about
categories and sellers needs `order_items` in between even though the question
never mentions items. Join lines inside each table chunk and the worked
examples are there to reduce that.

## Next

- `db/generate_distractors.py`: add about 12 and 37 look-alike tables for the
  RQ1 scaling study (25 and 50 tables in total).
- Tune `k` and chunking using `recall.py` once the model is downloaded.
