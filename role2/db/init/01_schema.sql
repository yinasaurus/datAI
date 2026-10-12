-- Olist marketplace schema: 9 tables from the public Olist dataset plus 4 synthetic tables.
-- This file only creates empty tables. Data comes from db/load_olist.py and
-- db/generate_synthetic.py, which run from your machine after the container is up.
-- Table and column descriptions live in schema_rag/schema_docs.yaml.

-- Olist tables -------------------------------------------------------------

CREATE TABLE product_category_translation (
    product_category_name TEXT PRIMARY KEY,
    product_category_name_english TEXT NOT NULL
);

CREATE TABLE geolocation (
    zip_code_prefix CHAR(5) PRIMARY KEY,
    lat DOUBLE PRECISION NOT NULL,
    lng DOUBLE PRECISION NOT NULL,
    city TEXT NOT NULL,
    state CHAR(2) NOT NULL
);

CREATE TABLE customers (
    customer_id TEXT PRIMARY KEY,
    customer_unique_id TEXT NOT NULL,
    customer_zip_code_prefix CHAR(5) NOT NULL,
    customer_city TEXT NOT NULL,
    customer_state CHAR(2) NOT NULL
);

CREATE TABLE sellers (
    seller_id TEXT PRIMARY KEY,
    seller_zip_code_prefix CHAR(5) NOT NULL,
    seller_city TEXT NOT NULL,
    seller_state CHAR(2) NOT NULL
);

CREATE TABLE products (
    product_id TEXT PRIMARY KEY,
    product_category_name TEXT REFERENCES product_category_translation (product_category_name),
    product_name_length INTEGER,
    product_description_length INTEGER,
    product_photos_qty INTEGER,
    product_weight_g INTEGER,
    product_length_cm INTEGER,
    product_height_cm INTEGER,
    product_width_cm INTEGER
);

CREATE TABLE orders (
    order_id TEXT PRIMARY KEY,
    customer_id TEXT NOT NULL REFERENCES customers (customer_id),
    order_status TEXT NOT NULL,
    order_purchase_timestamp TIMESTAMP NOT NULL,
    order_approved_at TIMESTAMP,
    order_delivered_carrier_date TIMESTAMP,
    order_delivered_customer_date TIMESTAMP,
    order_estimated_delivery_date TIMESTAMP NOT NULL
);

CREATE TABLE order_items (
    order_id TEXT NOT NULL REFERENCES orders (order_id),
    order_item_id INTEGER NOT NULL,
    product_id TEXT NOT NULL REFERENCES products (product_id),
    seller_id TEXT NOT NULL REFERENCES sellers (seller_id),
    shipping_limit_date TIMESTAMP NOT NULL,
    price NUMERIC(10, 2) NOT NULL,
    freight_value NUMERIC(10, 2) NOT NULL,
    PRIMARY KEY (order_id, order_item_id)
);

CREATE TABLE order_payments (
    order_id TEXT NOT NULL REFERENCES orders (order_id),
    payment_sequential INTEGER NOT NULL,
    payment_type TEXT NOT NULL,
    payment_installments INTEGER NOT NULL,
    payment_value NUMERIC(10, 2) NOT NULL,
    PRIMARY KEY (order_id, payment_sequential)
);

-- review_id is not unique in Olist: a few reviews cover several orders.
CREATE TABLE order_reviews (
    review_id TEXT NOT NULL,
    order_id TEXT NOT NULL REFERENCES orders (order_id),
    review_score SMALLINT NOT NULL CHECK (review_score BETWEEN 1 AND 5),
    review_comment_title TEXT,
    review_comment_message TEXT,
    review_creation_date TIMESTAMP NOT NULL,
    review_answer_timestamp TIMESTAMP,
    PRIMARY KEY (review_id, order_id)
);

-- Synthetic tables (fake data from Faker, seed 42) --------------------------

CREATE TABLE customer_contacts (
    customer_id TEXT PRIMARY KEY REFERENCES customers (customer_id),
    email TEXT NOT NULL,       -- sensitive
    phone TEXT NOT NULL,       -- sensitive
    marketing_opt_in BOOLEAN NOT NULL
);

CREATE TABLE staff (
    staff_id INTEGER PRIMARY KEY,
    full_name TEXT NOT NULL,
    job_title TEXT NOT NULL,
    region_state CHAR(2) NOT NULL,
    hired_on DATE NOT NULL,
    salary NUMERIC(10, 2) NOT NULL,   -- sensitive
    national_id TEXT NOT NULL         -- sensitive
);

CREATE TABLE seller_payout_accounts (
    seller_id TEXT PRIMARY KEY REFERENCES sellers (seller_id),
    account_manager_id INTEGER NOT NULL REFERENCES staff (staff_id),
    bank_name TEXT NOT NULL,
    bank_code CHAR(3) NOT NULL,        -- sensitive
    account_number TEXT NOT NULL,      -- sensitive
    payout_frequency TEXT NOT NULL
);

CREATE TABLE returns (
    return_id INTEGER PRIMARY KEY,
    order_id TEXT NOT NULL,
    order_item_id INTEGER NOT NULL,
    requested_at TIMESTAMP NOT NULL,
    reason TEXT NOT NULL,
    status TEXT NOT NULL,
    refund_amount NUMERIC(10, 2),
    FOREIGN KEY (order_id, order_item_id) REFERENCES order_items (order_id, order_item_id)
);

-- Indexes for the joins the agent writes most often.
CREATE INDEX ON orders (customer_id);
CREATE INDEX ON order_items (product_id);
CREATE INDEX ON order_items (seller_id);
CREATE INDEX ON order_reviews (order_id);
CREATE INDEX ON returns (order_id, order_item_id);
CREATE INDEX ON customers (customer_zip_code_prefix);
CREATE INDEX ON sellers (seller_zip_code_prefix);
