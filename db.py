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
    _run_migrations(conn)
    conn.commit()
    conn.close()


def _run_migrations(conn):
    """Doplni sloupce, ktere pribyly po prvnim nasazeni, do jiz existujici databaze
    (CREATE TABLE IF NOT EXISTS sloupce k existujici tabulce nedoplni, proto rucni migrace)."""
    existing_cols = {row[1] for row in conn.execute("PRAGMA table_info(user_settings)").fetchall()}
    if "chat_widget_enabled" not in existing_cols:
        conn.execute("ALTER TABLE user_settings ADD COLUMN chat_widget_enabled INTEGER DEFAULT 1")


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
