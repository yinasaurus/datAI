-- Tiny stand-in for the Olist database.
-- Two tables are enough to test a join, an error message, and a repair.
-- Role 1 replaces this file with the 9 Olist tables plus 4 synthetic tables.

CREATE TABLE orders (
    order_id INTEGER PRIMARY KEY,
    customer_id INTEGER NOT NULL,
    status TEXT NOT NULL,
    purchased_at DATE NOT NULL
);

CREATE TABLE order_items (
    item_id INTEGER PRIMARY KEY,
    order_id INTEGER NOT NULL REFERENCES orders (order_id),
    product_id INTEGER NOT NULL,
    price NUMERIC(10, 2) NOT NULL
);

INSERT INTO orders (order_id, customer_id, status, purchased_at) VALUES
    (1, 10, 'delivered', '2018-01-05'),
    (2, 11, 'shipped', '2018-02-11'),
    (3, 10, 'canceled', '2018-03-02');

INSERT INTO order_items (item_id, order_id, product_id, price) VALUES
    (1, 1, 100, 29.90),
    (2, 1, 101, 15.00),
    (3, 2, 100, 29.90);
