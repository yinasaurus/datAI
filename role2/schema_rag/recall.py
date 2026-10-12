"""Schema recall@k on a small set of hand-labelled questions.

    python -m schema_rag.recall            # k = 1..8
    python -m schema_rag.recall --k 4

Recall@k for one question is the share of its gold tables that appear among
the top-k chunks (an example chunk counts for every table it lists). This is a
quick check while tuning retrieval; the full benchmark lives with Role 4.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from interfaces.types import SchemaChunk

# question -> tables a correct query needs. Not the same as the worked examples.
DEV_QUESTIONS: list[tuple[str, set[str]]] = [
    ("How many orders were canceled?", {"orders"}),
    ("What is the average freight cost per item?", {"order_items"}),
    ("Which state has the most customers?", {"customers"}),
    ("How many sellers are based in Sao Paulo state?", {"sellers"}),
    ("What is the average review score for orders that arrived late?", {"order_reviews", "orders"}),
    ("Which sellers sold the most items in the furniture_decor category?", {"order_items", "products", "product_category_translation"}),
    ("What was total revenue per month in 2017?", {"order_items", "orders"}),
    ("How many orders were paid with boleto in each state?", {"order_payments", "orders", "customers"}),
    ("Which product categories have the highest return rate?", {"returns", "order_items", "products", "product_category_translation"}),
    ("How many customers opted in to marketing emails?", {"customer_contacts"}),
    ("Which account managers look after the most sellers?", {"staff", "seller_payout_accounts"}),
    ("How many sellers are paid weekly?", {"seller_payout_accounts"}),
    ("What is the average delivery time in days for each seller state?", {"orders", "order_items", "sellers"}),
    ("Which cities have the heaviest products shipped to them?", {"products", "order_items", "orders", "customers"}),
    ("What are the latitude and longitude of sellers in Curitiba?", {"sellers", "geolocation"}),
    ("What share of returns were refunded, by reason?", {"returns"}),
]


def tables_in(chunk: SchemaChunk) -> set[str]:
    return set(chunk.source.split(","))


def recall_at_k(retrieve, k: int, questions=DEV_QUESTIONS) -> tuple[float, list[tuple[str, float, set[str]]]]:
    rows = []
    for question, gold in questions:
        found: set[str] = set()
        for chunk in retrieve(question, k):
            found |= tables_in(chunk)
        rows.append((question, len(gold & found) / len(gold), gold - found))
    return sum(score for _q, score, _m in rows) / len(rows), rows


def main() -> int:
    parser = argparse.ArgumentParser(description="Schema recall@k on the dev questions.")
    parser.add_argument("--k", type=int, help="one k to report in detail")
    args = parser.parse_args()

    from interfaces.retriever import retrieve

    if args.k:
        mean, rows = recall_at_k(retrieve, args.k)
        for question, score, missed in rows:
            note = f"  missed: {', '.join(sorted(missed))}" if missed else ""
            print(f"{score:4.2f}  {question}{note}")
        print(f"\nrecall@{args.k} = {mean:.3f}")
    else:
        for k in range(1, 9):
            print(f"recall@{k} = {recall_at_k(retrieve, k)[0]:.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
