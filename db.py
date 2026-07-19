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

    cal_cols = {row[1] for row in conn.execute("PRAGMA table_info(calendar_events)").fetchall()}
    if "color" not in cal_cols:
        conn.execute("ALTER TABLE calendar_events ADD COLUMN color TEXT DEFAULT '#7ed957'")
    if "icon" not in cal_cols:
        conn.execute("ALTER TABLE calendar_events ADD COLUMN icon TEXT DEFAULT '📌'")
    if "priority" not in cal_cols:
        conn.execute("ALTER TABLE calendar_events ADD COLUMN priority TEXT DEFAULT 'medium'")

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
    if "is_banned" not in user_cols:
        conn.execute("ALTER TABLE users ADD COLUMN is_banned INTEGER DEFAULT 0")
    if "avatar_position" not in user_cols:
        conn.execute("ALTER TABLE users ADD COLUMN avatar_position TEXT DEFAULT '50% 50%'")
    if "banner_position" not in user_cols:
        conn.execute("ALTER TABLE users ADD COLUMN banner_position TEXT DEFAULT '50% 50%'")

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

    challenge_count = conn.execute("SELECT COUNT(*) FROM challenges").fetchone()[0]
    if challenge_count == 0:
        seed_challenges = [
            ("first_trade", "První obchod", "Zapiš svůj první obchod do deníku.", 20, 1, "trades", 0),
            ("trades_5", "Rozjetý deník", "Zapiš celkem 5 obchodů.", 50, 5, "trades", 0),
            ("trades_25", "Zkušený trader", "Zapiš celkem 25 obchodů.", 150, 25, "trades", 0),
            ("trades_100", "Veterán", "Zapiš celkem 100 obchodů.", 400, 100, "trades", 0),
            ("winrate_60", "Ostrá muška", "Dosáhni winrate 60 % (min. 10 obchodů).", 150, 60, "winrate", 10),
            ("starting_capital", "Připraven na start", "Nastav si počáteční kapitál v nastavení profilu.", 10, 1, "has_capital", 0),
            ("friends_3", "Parta se sejde", "Přidej si 3 kamarády.", 30, 3, "friends", 0),
            ("friends_10", "Sociální motýl", "Přidej si 10 kamarádů.", 100, 10, "friends", 0),
            ("first_post", "První příspěvek", "Napiš první příspěvek na feed.", 20, 1, "posts", 0),
            ("posts_10", "Influencer", "Napiš celkem 10 příspěvků na feed.", 80, 10, "posts", 0),
            ("messages_10", "Ukecaný", "Pošli celkem 10 zpráv.", 20, 10, "messages", 0),
            ("calendar_event", "Organizovaný", "Vytvoř první událost v kalendáři.", 15, 1, "calendar_events", 0),
            ("calendar_invite", "Týmový hráč", "Pozvi kamaráda do kalendářové události.", 25, 1, "calendar_invites_sent", 0),
        ]
        conn.executemany(
            """INSERT INTO challenges (challenge_key, title, description, points, target, stat, min_trades)
               VALUES (?,?,?,?,?,?,?)""",
            seed_challenges,
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
