-- ============================================================
-- Simple E-commerce database (MySQL 8.x)
-- Run:  mysql -u root -p < ecommerce_db.sql
-- ============================================================

DROP DATABASE IF EXISTS ecommerce;
CREATE DATABASE ecommerce CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE ecommerce;

-- ---------- TABLES ----------

CREATE TABLE customers (
    customer_id   INT AUTO_INCREMENT PRIMARY KEY,
    first_name    VARCHAR(50)  NOT NULL,
    last_name     VARCHAR(50)  NOT NULL,
    email         VARCHAR(100) NOT NULL UNIQUE,
    phone         VARCHAR(20),
    city          VARCHAR(50),
    state         VARCHAR(50),
    created_at    DATE NOT NULL
);

CREATE TABLE categories (
    category_id   INT AUTO_INCREMENT PRIMARY KEY,
    name          VARCHAR(50) NOT NULL UNIQUE
);

CREATE TABLE products (
    product_id    INT AUTO_INCREMENT PRIMARY KEY,
    name          VARCHAR(100) NOT NULL,
    category_id   INT NOT NULL,
    price         DECIMAL(10,2) NOT NULL,
    stock_qty     INT NOT NULL DEFAULT 0,
    FOREIGN KEY (category_id) REFERENCES categories(category_id)
);

CREATE TABLE orders (
    order_id      INT AUTO_INCREMENT PRIMARY KEY,
    customer_id   INT NOT NULL,
    order_date    DATE NOT NULL,
    status        ENUM('pending','shipped','delivered','cancelled') NOT NULL,
    total_amount  DECIMAL(12,2) NOT NULL DEFAULT 0,
    FOREIGN KEY (customer_id) REFERENCES customers(customer_id)
);

CREATE TABLE order_items (
    order_item_id INT AUTO_INCREMENT PRIMARY KEY,
    order_id      INT NOT NULL,
    product_id    INT NOT NULL,
    quantity      INT NOT NULL,
    unit_price    DECIMAL(10,2) NOT NULL,
    FOREIGN KEY (order_id)   REFERENCES orders(order_id),
    FOREIGN KEY (product_id) REFERENCES products(product_id)
);

CREATE TABLE payments (
    payment_id    INT AUTO_INCREMENT PRIMARY KEY,
    order_id      INT NOT NULL,
    amount        DECIMAL(12,2) NOT NULL,
    method        ENUM('UPI','Credit Card','Cash on Delivery') NOT NULL,
    status        ENUM('pending','paid','failed') NOT NULL,
    paid_at       DATE,
    FOREIGN KEY (order_id) REFERENCES orders(order_id)
);

CREATE TABLE reviews (
    review_id     INT AUTO_INCREMENT PRIMARY KEY,
    product_id    INT NOT NULL,
    customer_id   INT NOT NULL,
    rating        TINYINT NOT NULL CHECK (rating BETWEEN 1 AND 5),
    comment       VARCHAR(255),
    created_at    DATE NOT NULL,
    FOREIGN KEY (product_id)  REFERENCES products(product_id),
    FOREIGN KEY (customer_id) REFERENCES customers(customer_id)
);

-- ---------- SAMPLE DATA ----------

INSERT INTO customers (first_name, last_name, email, phone, city, state, created_at) VALUES
('Arun',    'Kumar',   'arun.kumar@example.com',   '9876500001', 'Coimbatore', 'Tamil Nadu', '2025-11-02'),
('Priya',   'Sharma',  'priya.sharma@example.com', '9876500002', 'Chennai',    'Tamil Nadu', '2025-12-15'),
('Rahul',   'Verma',   'rahul.verma@example.com',  '9876500003', 'Mumbai',     'Maharashtra','2026-01-10'),
('Sneha',   'Reddy',   'sneha.reddy@example.com',  '9876500004', 'Hyderabad',  'Telangana',  '2026-01-22'),
('Vikram',  'Singh',   'vikram.singh@example.com', '9876500005', 'Delhi',      'Delhi',      '2026-02-05'),
('Meena',   'Iyer',    'meena.iyer@example.com',   '9876500006', 'Bengaluru',  'Karnataka',  '2026-02-18'),
('Karthik', 'Raj',     'karthik.raj@example.com',  '9876500007', 'Madurai',    'Tamil Nadu', '2026-03-03'),
('Anita',   'Desai',   'anita.desai@example.com',  '9876500008', 'Pune',       'Maharashtra','2026-03-27'),
('Suresh',  'Nair',    'suresh.nair@example.com',  '9876500009', 'Kochi',      'Kerala',     '2026-04-11'),
('Divya',   'Menon',   'divya.menon@example.com',  '9876500010', 'Coimbatore', 'Tamil Nadu', '2026-05-09');

INSERT INTO categories (name) VALUES
('Electronics'), ('Clothing'), ('Books'), ('Home & Kitchen');

INSERT INTO products (name, category_id, price, stock_qty) VALUES
('Wireless Mouse',            1,  799.00, 120),
('Bluetooth Headphones',      1, 2499.00,  60),
('USB-C Fast Charger',        1, 1299.00,  90),
('Smart Watch',               1, 5999.00,  25),
('Cotton T-Shirt',            2,  499.00, 200),
('Denim Jeans',               2, 1499.00,  80),
('Running Shoes',             2, 2999.00,  45),
('Python Programming Book',   3,  599.00,  70),
('SQL Mastery Book',          3,  499.00,  55),
('Stainless Steel Bottle',    4,  699.00, 150),
('Coffee Maker',              4, 3499.00,  30),
('LED Desk Lamp',             4, 1199.00,  65);

INSERT INTO orders (customer_id, order_date, status) VALUES
(1,  '2026-01-05', 'delivered'),
(2,  '2026-01-18', 'delivered'),
(3,  '2026-02-02', 'delivered'),
(4,  '2026-02-14', 'delivered'),
(5,  '2026-03-01', 'delivered'),
(1,  '2026-03-12', 'delivered'),
(6,  '2026-04-04', 'delivered'),
(7,  '2026-04-20', 'shipped'),
(8,  '2026-05-08', 'delivered'),
(9,  '2026-05-19', 'cancelled'),
(10, '2026-06-02', 'delivered'),
(2,  '2026-06-25', 'shipped'),
(3,  '2026-07-09', 'delivered'),
(5,  '2026-09-15', 'pending'),
(4,  '2026-10-10', 'shipped');

-- order_items: unit_price is copied from products at time of sale
INSERT INTO order_items (order_id, product_id, quantity, unit_price)
SELECT v.o, v.p, v.q, pr.price
FROM (
    SELECT 1 o, 1 p, 1 q  UNION ALL SELECT 1, 3, 1
    UNION ALL SELECT 2, 2, 1
    UNION ALL SELECT 3, 5, 2  UNION ALL SELECT 3, 6, 1
    UNION ALL SELECT 4, 4, 1
    UNION ALL SELECT 5, 8, 1  UNION ALL SELECT 5, 9, 1
    UNION ALL SELECT 6, 7, 1
    UNION ALL SELECT 7, 10, 2 UNION ALL SELECT 7, 12, 1
    UNION ALL SELECT 8, 11, 1
    UNION ALL SELECT 9, 2, 1  UNION ALL SELECT 9, 3, 1
    UNION ALL SELECT 10, 5, 3
    UNION ALL SELECT 11, 6, 1 UNION ALL SELECT 11, 7, 1
    UNION ALL SELECT 12, 9, 2
    UNION ALL SELECT 13, 1, 1
    UNION ALL SELECT 14, 4, 1
    UNION ALL SELECT 15, 10, 1 UNION ALL SELECT 15, 8, 1
) v
JOIN products pr ON pr.product_id = v.p;

-- compute order totals from items
UPDATE orders o
JOIN (
    SELECT order_id, SUM(quantity * unit_price) AS total
    FROM order_items GROUP BY order_id
) t ON t.order_id = o.order_id
SET o.total_amount = t.total;

-- payments for every non-cancelled order
INSERT INTO payments (order_id, amount, method, status, paid_at)
SELECT order_id,
       total_amount,
       ELT(1 + MOD(order_id, 3), 'UPI', 'Credit Card', 'Cash on Delivery'),
       IF(status = 'pending', 'pending', 'paid'),
       IF(status = 'pending', NULL, order_date)
FROM orders
WHERE status <> 'cancelled';

INSERT INTO reviews (product_id, customer_id, rating, comment, created_at) VALUES
(1, 1, 5, 'Smooth and responsive',          '2026-01-12'),
(2, 2, 4, 'Great sound, average battery',   '2026-01-25'),
(4, 4, 5, 'Love the display',               '2026-02-22'),
(5, 3, 3, 'Fabric is okay',                 '2026-02-12'),
(7, 1, 5, 'Very comfortable for running',   '2026-03-20'),
(8, 5, 4, 'Good for beginners',             '2026-03-10'),
(10,6, 5, 'Keeps water cold all day',       '2026-04-12'),
(12,6, 4, 'Bright and sturdy',              '2026-04-12'),
(3, 8, 2, 'Heats up a bit',                 '2026-05-15'),
(6, 10,4, 'Good fit',                       '2026-06-10');

-- ---------- QUICK CHECKS ----------
-- SELECT COUNT(*) FROM customers;
-- SELECT c.first_name, SUM(o.total_amount) AS spent
--   FROM customers c JOIN orders o USING (customer_id)
--   WHERE o.status <> 'cancelled' GROUP BY c.customer_id ORDER BY spent DESC;
