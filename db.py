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
    if "notify_sound_enabled" not in existing_cols:
        conn.execute("ALTER TABLE user_settings ADD COLUMN notify_sound_enabled INTEGER DEFAULT 1")

    msg_cols = {row[1] for row in conn.execute("PRAGMA table_info(messages)").fetchall()}
    if "invite_id" not in msg_cols:
        conn.execute("ALTER TABLE messages ADD COLUMN invite_id INTEGER")

    user_cols = {row[1] for row in conn.execute("PRAGMA table_info(users)").fetchall()}
    if "points" not in user_cols:
        conn.execute("ALTER TABLE users ADD COLUMN points INTEGER DEFAULT 0")
    if "is_admin" not in user_cols:
        conn.execute("ALTER TABLE users ADD COLUMN is_admin INTEGER DEFAULT 0")
    if "has_seen_tutorial" not in user_cols:
        conn.execute("ALTER TABLE users ADD COLUMN has_seen_tutorial INTEGER DEFAULT 0")
    if "banner_path" not in user_cols:
        conn.execute("ALTER TABLE users ADD COLUMN banner_path TEXT")
    if "selected_banner_key" not in user_cols:
        conn.execute("ALTER TABLE users ADD COLUMN selected_banner_key TEXT")

    # Prvni naplneni obchodu puvodnimi odznaky (jen pokud je tabulka jeste prazdna,
    # aby se to nespoustelo opakovane a neduplikovalo pri kazdem startu appky)
    shop_count = conn.execute("SELECT COUNT(*) FROM shop_items").fetchone()[0]
    if shop_count == 0:
        seed_items = [
            ("badge_rocket", "badge", "Rocket", "Odznak k tvému jménu na profilu.", "🚀", 50),
            ("badge_fire", "badge", "On Fire", "Pro ty na winning streaku.", "🔥", 60),
            ("badge_bull", "badge", "Bull", "Věčný optimista.", "🐂", 80),
            ("badge_bear", "badge", "Bear", "Věčný pesimista.", "🐻", 80),
            ("badge_diamond", "badge", "Diamond Hands", "Nikdy neprodává se ztrátou (aspoň psychicky).", "💎", 100),
            ("badge_shark", "badge", "Shark", "Loví příležitosti na trhu.", "🦈", 100),
            ("badge_crown", "badge", "King", "Protože si to zasloužíš.", "👑", 250),
        ]
        conn.executemany(
            "INSERT INTO shop_items (item_key, kind, name, description, emoji, cost) VALUES (?,?,?,?,?,?)",
            seed_items,
        )


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
