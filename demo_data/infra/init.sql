CREATE SCHEMA IF NOT EXISTS finance;

CREATE TABLE IF NOT EXISTS public.orders (
  order_id SERIAL PRIMARY KEY,
  customer_id INT NOT NULL,
  order_total NUMERIC(10, 2) NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS public.customers (
  customer_id SERIAL PRIMARY KEY,
  full_name TEXT NOT NULL,
  email TEXT NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS public.inventory (
  inventory_id SERIAL PRIMARY KEY,
  sku TEXT NOT NULL,
  quantity INT NOT NULL,
  updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS finance.transactions (
  txn_id SERIAL PRIMARY KEY,
  account_id INT NOT NULL,
  amount NUMERIC(12, 2) NOT NULL,
  currency TEXT NOT NULL,
  txn_ts TIMESTAMP NOT NULL DEFAULT NOW()
);

INSERT INTO public.orders (customer_id, order_total) VALUES
  (1, 125.50),
  (2, 42.00),
  (3, 77.25);

INSERT INTO public.customers (full_name, email) VALUES
  ('Ada Lovelace', 'ada@example.com'),
  ('Grace Hopper', 'grace@example.com'),
  ('Katherine Johnson', 'kj@example.com');

INSERT INTO public.inventory (sku, quantity) VALUES
  ('SKU-001', 120),
  ('SKU-002', 50),
  ('SKU-003', 75);

INSERT INTO finance.transactions (account_id, amount, currency) VALUES
  (101, 1500.00, 'USD'),
  (102, 235.75, 'USD'),
  (103, 89.99, 'USD');
