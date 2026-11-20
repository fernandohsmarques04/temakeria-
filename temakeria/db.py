import sqlite3
from contextlib import closing
from pathlib import Path

from flask import current_app, g


SCHEMA = """
CREATE TABLE IF NOT EXISTS categories (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL COLLATE NOCASE UNIQUE,
    visible INTEGER NOT NULL CHECK (visible IN (0, 1))
);
CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY,
    category_id INTEGER NOT NULL REFERENCES categories(id),
    name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    price_cents INTEGER CHECK (price_cents >= 0),
    price_from INTEGER NOT NULL DEFAULT 0 CHECK (price_from IN (0, 1)),
    available INTEGER NOT NULL CHECK (available IN (0, 1)),
    asset TEXT,
    photo BLOB,
    CHECK (available = 0 OR price_cents IS NOT NULL),
    CHECK (asset IS NULL OR photo IS NULL)
);
CREATE INDEX IF NOT EXISTS product_category ON products(category_id);
CREATE TABLE IF NOT EXISTS administrator (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    password_hash TEXT NOT NULL,
    session_key TEXT NOT NULL
);
"""

INITIAL_CATALOG = {
    "Combinados": [
        ("Combinado do Chef", "combinado-chef.webp"),
        ("Combinado Tradicional", "combinado-tradicional.webp"),
    ],
    "Pokes": [
        ("Poke de camarão", "poke-camarao.webp"),
        ("Poke de salmão", "poke-salmao.webp"),
    ],
    "Sushis & niguiris": [("Niguiris", "niguiris.webp")],
    "Especiais": [
        ("Peças especiais", "especiais.webp"),
        ("Sushi no copo", "sushi-copo.webp"),
    ],
}


def connect(path):
    db = sqlite3.connect(path, timeout=10)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    return db


def initialize(path):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with closing(connect(path)) as db:
        db.execute("PRAGMA journal_mode = WAL")
        db.executescript(SCHEMA)
        with db:
            db.execute("BEGIN IMMEDIATE")
            if db.execute("PRAGMA user_version").fetchone()[0] != 0:
                return
            for category, products in INITIAL_CATALOG.items():
                category_id = db.execute(
                    "INSERT INTO categories (name, visible) VALUES (?, 1)", (category,)
                ).lastrowid
                db.executemany(
                    "INSERT INTO products (category_id, name, available, asset) VALUES (?, ?, 0, ?)",
                    [(category_id, name, asset) for name, asset in products],
                )
                if category == "Combinados":
                    db.execute(
                        """INSERT INTO products
                           (category_id, name, description, price_cents, price_from, available, asset)
                           VALUES (?, ?, ?, 15000, 1, 1, 'combinado-chef.webp')""",
                        (
                            category_id,
                            "Surpresa do Cheff",
                            "Uma seleção surpresa de sushis em 30, 50 ou 100 peças. "
                            "Consulte os valores de cada tamanho.",
                        ),
                    )
            db.execute("PRAGMA user_version = 1")


def get_db():
    if "db" not in g:
        g.db = connect(current_app.config["DATABASE"])
    return g.db


def close_db(error):
    db = g.pop("db", None)
    if db is not None:
        db.close()
