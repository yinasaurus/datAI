"""Fill the 4 synthetic tables with fake data (Faker, fixed seed).

    python db/generate_synthetic.py

Run after db/load_olist.py. Every name, email, phone number, ID number,
salary and bank detail here is fake. They exist so the guardrails have
sensitive columns to protect: customer_contacts.email and .phone,
staff.salary and .national_id, seller_payout_accounts.bank_code and
.account_number. Running it again replaces the 4 tables with the same rows.
"""

from __future__ import annotations

import random
import sys
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from db.load_olist import copy_rows, database_url

SEED = 42
STAFF_COUNT = 60
RETURN_RATE = 0.03

JOB_TITLES = ["Account Manager", "Senior Account Manager", "Seller Success Lead"]
BANKS = [("001", "Banco do Brasil"), ("033", "Santander"), ("104", "Caixa"), ("237", "Bradesco"), ("341", "Itau")]
PAYOUT_FREQUENCIES = ["weekly", "biweekly", "monthly"]
RETURN_REASONS = ["damaged", "wrong item", "not as described", "arrived late", "changed mind"]
RETURN_STATUSES = ["requested", "approved", "rejected", "refunded"]


def main() -> int:
    import psycopg
    from faker import Faker

    fake = Faker("pt_BR")
    Faker.seed(SEED)
    rng = random.Random(SEED)

    with psycopg.connect(database_url()) as conn, conn.cursor() as cursor:
        cursor.execute("SELECT customer_id FROM customers ORDER BY customer_id")
        customer_ids = [row[0] for row in cursor.fetchall()]
        cursor.execute("SELECT seller_id, seller_state FROM sellers ORDER BY seller_id")
        sellers = cursor.fetchall()
        cursor.execute(
            """
            SELECT i.order_id, i.order_item_id, i.price, o.order_delivered_customer_date
            FROM order_items AS i
            JOIN orders AS o ON o.order_id = i.order_id
            WHERE o.order_status = 'delivered' AND o.order_delivered_customer_date IS NOT NULL
            ORDER BY i.order_id, i.order_item_id
            """
        )
        delivered_items = cursor.fetchall()
        if not customer_ids or not sellers:
            sys.exit("The Olist tables are empty. Run python db/load_olist.py first.")

        cursor.execute("TRUNCATE returns, seller_payout_accounts, staff, customer_contacts")

        contacts = [
            [customer_id, fake.unique.email(), fake.cellphone_number(), rng.random() < 0.4]
            for customer_id in customer_ids
        ]
        copy_rows(cursor, "customer_contacts", ["customer_id", "email", "phone", "marketing_opt_in"], contacts)

        states = sorted({state for _seller, state in sellers})
        staff = []
        for staff_id in range(1, STAFF_COUNT + 1):
            hired_on = fake.date_between_dates(date_start=date(2012, 1, 1), date_end=date(2018, 6, 30))
            salary = Decimal(rng.randrange(4_000_00, 18_000_00)) / 100
            staff.append(
                [staff_id, fake.name(), rng.choice(JOB_TITLES), rng.choice(states), hired_on, salary, fake.cpf()]
            )
        copy_rows(
            cursor,
            "staff",
            ["staff_id", "full_name", "job_title", "region_state", "hired_on", "salary", "national_id"],
            staff,
        )

        by_state: dict[str, list[int]] = {}
        for row in staff:
            by_state.setdefault(row[3], []).append(row[0])
        accounts = []
        for seller_id, state in sellers:
            manager = rng.choice(by_state.get(state) or [row[0] for row in staff])
            bank_code, bank_name = rng.choice(BANKS)
            account_number = f"{rng.randrange(10_000, 99_999_999)}-{rng.randrange(10)}"
            accounts.append(
                [seller_id, manager, bank_name, bank_code, account_number, rng.choice(PAYOUT_FREQUENCIES)]
            )
        copy_rows(
            cursor,
            "seller_payout_accounts",
            ["seller_id", "account_manager_id", "bank_name", "bank_code", "account_number", "payout_frequency"],
            accounts,
        )

        returns = []
        for order_id, order_item_id, price, delivered_at in delivered_items:
            if rng.random() >= RETURN_RATE:
                continue
            status = rng.choice(RETURN_STATUSES)
            refund = price if status == "refunded" else None
            requested_at = delivered_at + timedelta(days=rng.randint(1, 30), minutes=rng.randint(0, 1439))
            returns.append(
                [len(returns) + 1, order_id, order_item_id, requested_at, rng.choice(RETURN_REASONS), status, refund]
            )
        copy_rows(
            cursor,
            "returns",
            ["return_id", "order_id", "order_item_id", "requested_at", "reason", "status", "refund_amount"],
            returns,
        )

    print(f"customer_contacts       {len(contacts):>8} rows")
    print(f"staff                   {len(staff):>8} rows")
    print(f"seller_payout_accounts  {len(accounts):>8} rows")
    print(f"returns                 {len(returns):>8} rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
