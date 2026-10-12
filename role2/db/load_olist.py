"""Load the 9 Olist CSVs into PostgreSQL.

    python db/load_olist.py                # reads role2/data/raw/
    python db/load_olist.py --raw ~/olist  # or another folder
    python db/load_olist.py --download     # fetch the CSVs first (no Kaggle login)

Start the database first (docker compose up -d). The tables come from
db/init/01_schema.sql. Running this again empties every table and reloads,
so the synthetic tables must be regenerated afterwards.

Cleaning done here, in the order the report should describe it:
- Zip code prefixes are zero-padded to 5 characters so every table agrees.
- Geolocation has about 1M rows with many per zip prefix. We keep one row per
  prefix: the mean latitude and longitude, and the most common city and state.
- Two product categories are missing from the translation file. They are added
  with a hand-written English name so the foreign key holds.
- The two misspelt product columns (``lenght``) are renamed to ``length``.
- Empty strings become NULL.
"""

from __future__ import annotations

import argparse
import csv
import os
import sys
from collections import Counter, defaultdict
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]

# Categories used in products but absent from product_category_name_translation.csv.
MISSING_TRANSLATIONS = {
    "pc_gamer": "pc_gamer",
    "portateis_cozinha_e_preparadores_de_alimentos": "portable_kitchen_and_food_preparers",
}

# table -> (csv file, csv columns in file order, table columns in the same order, primary key)
OLIST_FILES: dict[str, tuple[str, list[str], list[str], list[str]]] = {
    "product_category_translation": (
        "product_category_name_translation.csv",
        ["product_category_name", "product_category_name_english"],
        ["product_category_name", "product_category_name_english"],
        ["product_category_name"],
    ),
    "customers": (
        "olist_customers_dataset.csv",
        ["customer_id", "customer_unique_id", "customer_zip_code_prefix", "customer_city", "customer_state"],
        ["customer_id", "customer_unique_id", "customer_zip_code_prefix", "customer_city", "customer_state"],
        ["customer_id"],
    ),
    "sellers": (
        "olist_sellers_dataset.csv",
        ["seller_id", "seller_zip_code_prefix", "seller_city", "seller_state"],
        ["seller_id", "seller_zip_code_prefix", "seller_city", "seller_state"],
        ["seller_id"],
    ),
    "products": (
        "olist_products_dataset.csv",
        [
            "product_id", "product_category_name", "product_name_lenght", "product_description_lenght",
            "product_photos_qty", "product_weight_g", "product_length_cm", "product_height_cm",
            "product_width_cm",
        ],
        [
            "product_id", "product_category_name", "product_name_length", "product_description_length",
            "product_photos_qty", "product_weight_g", "product_length_cm", "product_height_cm",
            "product_width_cm",
        ],
        ["product_id"],
    ),
    "orders": (
        "olist_orders_dataset.csv",
        [
            "order_id", "customer_id", "order_status", "order_purchase_timestamp", "order_approved_at",
            "order_delivered_carrier_date", "order_delivered_customer_date",
            "order_estimated_delivery_date",
        ],
        [
            "order_id", "customer_id", "order_status", "order_purchase_timestamp", "order_approved_at",
            "order_delivered_carrier_date", "order_delivered_customer_date",
            "order_estimated_delivery_date",
        ],
        ["order_id"],
    ),
    "order_items": (
        "olist_order_items_dataset.csv",
        ["order_id", "order_item_id", "product_id", "seller_id", "shipping_limit_date", "price", "freight_value"],
        ["order_id", "order_item_id", "product_id", "seller_id", "shipping_limit_date", "price", "freight_value"],
        ["order_id", "order_item_id"],
    ),
    "order_payments": (
        "olist_order_payments_dataset.csv",
        ["order_id", "payment_sequential", "payment_type", "payment_installments", "payment_value"],
        ["order_id", "payment_sequential", "payment_type", "payment_installments", "payment_value"],
        ["order_id", "payment_sequential"],
    ),
    "order_reviews": (
        "olist_order_reviews_dataset.csv",
        [
            "review_id", "order_id", "review_score", "review_comment_title", "review_comment_message",
            "review_creation_date", "review_answer_timestamp",
        ],
        [
            "review_id", "order_id", "review_score", "review_comment_title", "review_comment_message",
            "review_creation_date", "review_answer_timestamp",
        ],
        ["review_id", "order_id"],
    ),
}

GEOLOCATION_FILE = "olist_geolocation_dataset.csv"
# Olist publishes the same 9 files on GitHub, so a Kaggle login is optional.
DOWNLOAD_URL = "https://raw.githubusercontent.com/olist/work-at-olist-data/master/datasets/{name}"
ZIP_COLUMNS = {"customer_zip_code_prefix", "seller_zip_code_prefix"}

# Parents before children, so foreign keys hold while loading.
LOAD_ORDER = [
    "product_category_translation",
    "geolocation",
    "customers",
    "sellers",
    "products",
    "orders",
    "order_items",
    "order_payments",
    "order_reviews",
]
ALL_TABLES = LOAD_ORDER + ["customer_contacts", "staff", "seller_payout_accounts", "returns"]


def database_url() -> str:
    load_dotenv(ROOT / ".env")
    url = os.environ.get("DATABASE_URL", "").strip()
    if not url:
        sys.exit("DATABASE_URL is not set. Copy role2/.env.example to role2/.env.")
    return url


def zip5(value: str) -> str:
    return value.strip().zfill(5)


def read_rows(path: Path, expected: list[str]):
    """Yield rows as lists, after checking the header matches what we expect."""
    # utf-8-sig drops the byte-order mark some Olist files start with.
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.reader(handle)
        header = next(reader)
        if header != expected:
            sys.exit(f"{path.name}: unexpected columns {header}. Expected {expected}.")
        for row in reader:
            yield [cell if cell != "" else None for cell in row]


def table_rows(table: str, raw: Path) -> list[list[object]]:
    filename, csv_columns, table_columns, key = OLIST_FILES[table]
    key_positions = [table_columns.index(column) for column in key]
    zip_positions = [i for i, column in enumerate(table_columns) if column in ZIP_COLUMNS]
    seen: set[tuple] = set()
    rows: list[list[object]] = []
    for row in read_rows(raw / filename, csv_columns):
        for i in zip_positions:
            row[i] = zip5(row[i])
        row_key = tuple(row[i] for i in key_positions)
        if row_key in seen:
            continue
        seen.add(row_key)
        rows.append(row)
    if table == "product_category_translation":
        present = {row[0] for row in rows}
        rows.extend([name, english] for name, english in MISSING_TRANSLATIONS.items() if name not in present)
    return rows


def geolocation_rows(raw: Path) -> list[list[object]]:
    """One row per zip prefix: mean coordinates, most common city and state."""
    expected = [
        "geolocation_zip_code_prefix", "geolocation_lat", "geolocation_lng",
        "geolocation_city", "geolocation_state",
    ]
    sums: dict[str, list[float]] = defaultdict(lambda: [0.0, 0.0, 0])
    places: dict[str, Counter] = defaultdict(Counter)
    for prefix, lat, lng, city, state in read_rows(raw / GEOLOCATION_FILE, expected):
        prefix = zip5(prefix)
        total = sums[prefix]
        total[0] += float(lat)
        total[1] += float(lng)
        total[2] += 1
        places[prefix][(city, state)] += 1
    rows = []
    for prefix, (lat_sum, lng_sum, count) in sorted(sums.items()):
        city, state = places[prefix].most_common(1)[0][0]
        rows.append([prefix, lat_sum / count, lng_sum / count, city, state])
    return rows


def download(raw: Path) -> None:
    import shutil
    import ssl
    from urllib.request import urlopen

    # Python from python.org on macOS ships without root certificates, so use
    # certifi's bundle (installed with google-genai) when it is available.
    try:
        import certifi

        context = ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        context = ssl.create_default_context()

    raw.mkdir(parents=True, exist_ok=True)
    names = [spec[0] for spec in OLIST_FILES.values()] + [GEOLOCATION_FILE]
    for name in names:
        if (raw / name).is_file():
            continue
        print(f"downloading {name}")
        partial = raw / (name + ".part")
        with urlopen(DOWNLOAD_URL.format(name=name), context=context) as response, partial.open("wb") as out:
            shutil.copyfileobj(response, out)
        partial.replace(raw / name)


def copy_rows(cursor, table: str, columns: list[str], rows: list[list[object]]) -> None:
    column_list = ", ".join(columns)
    with cursor.copy(f"COPY {table} ({column_list}) FROM STDIN") as copy:
        for row in rows:
            copy.write_row(row)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--raw", type=Path, default=ROOT / "data" / "raw", help="folder with the Olist CSVs")
    parser.add_argument("--download", action="store_true", help="download missing CSVs from Olist's GitHub")
    args = parser.parse_args()
    raw = args.raw.expanduser()
    if args.download:
        download(raw)

    missing = [name for name, *_ in OLIST_FILES.values() if not (raw / name).is_file()]
    if not (raw / GEOLOCATION_FILE).is_file():
        missing.append(GEOLOCATION_FILE)
    if missing:
        sys.exit(f"Missing in {raw}: {', '.join(missing)}. See data/README.md.")

    import psycopg

    with psycopg.connect(database_url()) as conn, conn.cursor() as cursor:
        cursor.execute(f"TRUNCATE {', '.join(ALL_TABLES)}")
        for table in LOAD_ORDER:
            if table == "geolocation":
                rows = geolocation_rows(raw)
                columns = ["zip_code_prefix", "lat", "lng", "city", "state"]
            else:
                rows = table_rows(table, raw)
                columns = OLIST_FILES[table][2]
            copy_rows(cursor, table, columns, rows)
            print(f"{table:30} {len(rows):>8} rows")
    print("Done. Next: python db/generate_synthetic.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
