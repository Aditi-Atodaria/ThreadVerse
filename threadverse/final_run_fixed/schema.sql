-- ============================================================
-- ThreadVerse — SQLite Schema (for reference only)
-- The app auto-creates and seeds this via db.init_db()
-- on first run. You do NOT need to run this manually.
-- ============================================================

CREATE TABLE IF NOT EXISTS users (
    id               TEXT PRIMARY KEY,
    name             TEXT NOT NULL,
    email            TEXT NOT NULL UNIQUE,
    password         TEXT NOT NULL,
    role             TEXT NOT NULL DEFAULT 'customer',
    shop_name        TEXT,
    created          TEXT,
    contact_number   TEXT,
    verification_doc TEXT,
    google_id        TEXT,
    is_verified      INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS products (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    category    TEXT NOT NULL,
    subcategory TEXT,
    gender      TEXT DEFAULT 'unisex',
    color       TEXT,
    sizes       TEXT,
    price       REAL NOT NULL,
    occasion    TEXT,
    tags        TEXT,
    rating      REAL DEFAULT 0,
    reviews     INTEGER DEFAULT 0,
    stock       INTEGER DEFAULT 0,
    image       TEXT,
    description TEXT,
    vendor_id   TEXT REFERENCES users(id),
    vendor_name TEXT
);

CREATE TABLE IF NOT EXISTS orders (
    id               TEXT PRIMARY KEY,
    user_id          TEXT REFERENCES users(id),
    total            REAL NOT NULL DEFAULT 0,
    status           TEXT DEFAULT 'Confirmed',
    date             TEXT,
    shipping_name    TEXT,
    shipping_address TEXT,
    shipping_city    TEXT
);

CREATE TABLE IF NOT EXISTS order_items (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id      TEXT REFERENCES orders(id) ON DELETE CASCADE,
    product_id    INTEGER REFERENCES products(id),
    name          TEXT,
    price         REAL,
    qty           INTEGER DEFAULT 1,
    selected_size TEXT,
    image         TEXT
);

CREATE TABLE IF NOT EXISTS cart (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id    TEXT NOT NULL,
    product_id    INTEGER REFERENCES products(id),
    name          TEXT,
    price         REAL,
    qty           INTEGER DEFAULT 1,
    selected_size TEXT,
    image         TEXT
);

CREATE TABLE IF NOT EXISTS wishlist (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id  TEXT NOT NULL,
    product_id  INTEGER REFERENCES products(id),
    name        TEXT,
    price       REAL,
    image       TEXT
);
