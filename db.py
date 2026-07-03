import sqlite3
from pathlib import Path
from flask import g, current_app

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "trader_hub.db"
SCHEMA_PATH = BASE_DIR / "schema.sql"


def get_db():
    """Vrati pripojeni k databazi pro aktualni request (znovupouzitelne)."""
    if "db" not in g:
        g.db = sqlite3.connect(str(DB_PATH))
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def close_db(e=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    """Vytvori databazi a tabulky, pokud jeste neexistuji. Bezpecne volat opakovane."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    conn.commit()
    _migrate(conn)
    conn.close()


def _migrate(conn):
    """Dopl\u0148uje nov\u00e9 sloupce do existuj\u00edc\u00edch tabulek (bezpe\u010dn\u00e9 opakovan\u00e9 vol\u00e1n\u00ed,
    nema\u017e\u00e1 \u017e\u00e1dn\u00e1 stars\u00ed data)."""
    wanted_columns = {
        "messages": [
            ("image_path", "TEXT"),
            ("gif_url", "TEXT"),
        ],
    }
    for table, columns in wanted_columns.items():
        existing = {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
        for name, coltype in columns:
            if name not in existing:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {coltype}")
    conn.commit()


def query_all(sql, params=()):
    db = get_db()
    return db.execute(sql, params).fetchall()


def query_one(sql, params=()):
    db = get_db()
    row = db.execute(sql, params).fetchone()
    return row


def execute(sql, params=()):
    db = get_db()
    cur = db.execute(sql, params)
    db.commit()
    return cur.lastrowid


def register_db(app):
    app.teardown_appcontext(close_db)
