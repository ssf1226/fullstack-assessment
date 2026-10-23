"""SQLite persistence for the Variant PDP backend.

We use a single SQLite database with three tables:
  products   - one product row (id, name, description, image)
  options    - option dimensions (color, size) per product
  skus       - concrete SKUs with id, price, available quantity, image, values

Cart state is intentionally kept in memory for this exercise (no user
auth/session layer is in scope); idempotency keys for add-to-cart are tracked
in a small table so that a repeated request key does not double-add.

Concurrency / overselling
-------------------------
Two concurrent requests must not both reserve the last unit. We enforce this
in `reserve_stock` by taking a process-wide lock and then running the check
and decrement inside a SQLite `BEGIN IMMEDIATE` transaction. SQLite's
`BEGIN IMMEDIATE` acquires the write lock immediately and serialises writers,
so even with a single file DB the final-unit race cannot oversell: the second
writer sees the already-decremented quantity and rejects.
"""

from __future__ import annotations

import os
import sqlite3
import threading

_SCHEMA = """
CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT NOT NULL,
    image TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS options (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER NOT NULL REFERENCES products(id),
    name TEXT NOT NULL,          -- e.g. "colour" | "size"
    value TEXT NOT NULL          -- e.g. "Red" | "S"
);
CREATE TABLE IF NOT EXISTS skus (
    id TEXT PRIMARY KEY,         -- e.g. "ts-red-s"
    product_id INTEGER NOT NULL REFERENCES products(id),
    price REAL NOT NULL,
    qty INTEGER NOT NULL,        -- available quantity
    image TEXT NOT NULL,
    colour TEXT NOT NULL,
    size TEXT NOT NULL,
    UNIQUE(product_id, colour, size)
);
CREATE TABLE IF NOT EXISTS idempotency_keys (
    key TEXT PRIMARY KEY,
    sku_id TEXT NOT NULL,
    quantity INTEGER NOT NULL
);
"""

_SEED = [
    # product
    (1, "Everyday Cotton Tee",
     "A soft, everyday cotton t-shirt available in a range of colours and sizes.",
     "https://images.unsplash.com/photo-1521572163474-6864f9cf17ab?w=600"),
    # options
    (1, "colour", "Red"), (1, "colour", "Blue"), (1, "colour", "Green"),
    (1, "size", "S"), (1, "size", "M"), (1, "size", "L"),
    # SKUs — one unavailable combination (Green-M has no SKU) and one
    # out-of-stock SKU (Green-S has qty 0).
    ("ts-red-s", 1, 19.99, 10, "https://images.unsplash.com/photo-1521572163474-6864f9cf17ab?w=400", "Red", "S"),
    ("ts-red-m", 1, 19.99, 8, "https://images.unsplash.com/photo-1521572163474-6864f9cf17ab?w=400", "Red", "M"),
    ("ts-red-l", 1, 21.99, 5, "https://images.unsplash.com/photo-1521572163474-6864f9cf17ab?w=400", "Red", "L"),
    ("ts-blue-s", 1, 19.99, 6, "https://images.unsplash.com/photo-1541099649105-f69ad21f3246?w=400", "Blue", "S"),
    ("ts-blue-m", 1, 20.99, 4, "https://images.unsplash.com/photo-1541099649105-f69ad21f3246?w=400", "Blue", "M"),
    ("ts-green-s", 1, 19.99, 0, "https://images.unsplash.com/photo-1620012253295-c15cc3e65df4?w=400", "Green", "S"),
]

# Unavailable combinations (no SKU exists) — surfaced to the frontend so it can
# disable them.
UNAVAILABLE_COMBOS: set[tuple[str, str]] = {
    ("Green", "M"),
    ("Green", "L"),
    ("Blue", "L"),
}


class DB:
    """Tiny wrapper around a SQLite connection (one connection per operation)."""

    def __init__(self, path: str):
        self._path = path
        self._lock = threading.Lock()
        self._init()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _init(self) -> None:
        with self._lock:
            conn = self._connect()
            try:
                conn.executescript(_SCHEMA)
                # Seed only when empty so a running DB is not reset.
                if conn.execute("SELECT COUNT(*) FROM products").fetchone()[0] == 0:
                    conn.execute(
                        "INSERT INTO products(id,name,description,image) VALUES(?,?,?,?)",
                        _SEED[0])
                    for pid, name, value in _SEED[1:7]:
                        conn.execute(
                            "INSERT INTO options(product_id,name,value) VALUES(?,?,?)",
                            (pid, name, value))
                    for row in _SEED[7:]:
                        conn.execute(
                            "INSERT INTO skus(id,product_id,price,qty,image,colour,size) "
                            "VALUES(?,?,?,?,?,?,?)",
                            row)
                conn.commit()
            finally:
                conn.close()

    def get_product(self, product_id: int):
        with self._lock:
            conn = self._connect()
            try:
                product = conn.execute(
                    "SELECT * FROM products WHERE id=?", (product_id,)).fetchone()
                if product is None:
                    return None
                options_rows = conn.execute(
                    "SELECT name, value FROM options WHERE product_id=? ORDER BY id",
                    (product_id,)).fetchall()
                skus_rows = conn.execute(
                    "SELECT id, price, qty, image, colour, size FROM skus "
                    "WHERE product_id=? ORDER BY id", (product_id,)).fetchall()
                return {
                    "id": product["id"],
                    "name": product["name"],
                    "description": product["description"],
                    "image": product["image"],
                    "options": _group_options(options_rows),
                    "skus": [
                        {
                            "id": s["id"],
                            "price": s["price"],
                            "available_quantity": s["qty"],
                            "image": s["image"],
                            "colour": s["colour"],
                            "size": s["size"],
                        }
                        for s in skus_rows
                    ],
                }
            finally:
                conn.close()

    def reserve_stock(self, sku_id: str, quantity: int) -> bool:
        """Atomically check and decrement stock. Returns False if insufficient."""
        with self._lock:
            conn = self._connect()
            try:
                conn.execute("BEGIN IMMEDIATE")  # serialise writers
                row = conn.execute(
                    "SELECT qty FROM skus WHERE id=?", (sku_id,)).fetchone()
                if row is None or row["qty"] < quantity:
                    conn.execute("ROLLBACK")
                    return False
                conn.execute(
                    "UPDATE skus SET qty = qty - ? WHERE id=?", (quantity, sku_id))
                conn.commit()
                return True
            finally:
                conn.close()

    def sku_exists(self, sku_id: str) -> bool:
        with self._lock:
            conn = self._connect()
            try:
                return conn.execute(
                    "SELECT 1 FROM skus WHERE id=?", (sku_id,)).fetchone() is not None
            finally:
                conn.close()

    # ---- idempotency keys for add-to-cart ----
    def remember_key(self, key: str, sku_id: str, quantity: int) -> bool:
        """Returns True if the key was newly inserted, False if it already existed."""
        with self._lock:
            conn = self._connect()
            try:
                try:
                    conn.execute(
                        "INSERT INTO idempotency_keys(key,sku_id,quantity) VALUES(?,?,?)",
                        (key, sku_id, quantity))
                    conn.commit()
                    return True
                except sqlite3.IntegrityError:
                    conn.rollback()
                    return False
            finally:
                conn.close()

    def get_key(self, key: str):
        with self._lock:
            conn = self._connect()
            try:
                row = conn.execute(
                    "SELECT sku_id, quantity FROM idempotency_keys WHERE key=?",
                    (key,)).fetchone()
                return None if row is None else (row["sku_id"], row["quantity"])
            finally:
                conn.close()


def _group_options(rows) -> list[dict]:
    by_name: dict[str, list[str]] = {}
    for r in rows:
        by_name.setdefault(r["name"], []).append(r["value"])
    return [{"name": name, "values": values} for name, values in by_name.items()]


# Path is overridable for tests (in-memory DB).
DEFAULT_DB_PATH = os.environ.get("PDP_DB_PATH", os.path.join(os.path.dirname(__file__), "app.db"))


def get_db() -> DB:
    if not hasattr(get_db, "_db"):
        get_db._db = DB(DEFAULT_DB_PATH)
    return get_db._db


def reset_db_for_tests(path=":memory:") -> DB:
    get_db._db = DB(path)
    return get_db._db
