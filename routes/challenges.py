from flask import Blueprint, render_template, request, redirect, url_for, flash, g

from db import query_one, query_all, execute
from helpers import login_required

bp = Blueprint("challenges_bp", __name__)

CHALLENGES = [
    {"key": "first_trade", "title": "První obchod", "desc": "Zapiš svůj první obchod do deníku.",
     "points": 20, "target": 1, "stat": "trades"},
    {"key": "trades_5", "title": "Rozjetý deník", "desc": "Zapiš celkem 5 obchodů.",
     "points": 50, "target": 5, "stat": "trades"},
    {"key": "trades_25", "title": "Zkušený trader", "desc": "Zapiš celkem 25 obchodů.",
     "points": 150, "target": 25, "stat": "trades"},
    {"key": "trades_100", "title": "Veterán", "desc": "Zapiš celkem 100 obchodů.",
     "points": 400, "target": 100, "stat": "trades"},
    {"key": "winrate_60", "title": "Ostrá muška", "desc": "Dosáhni winrate 60 % (min. 10 obchodů).",
     "points": 150, "target": 60, "stat": "winrate", "min_trades": 10},
    {"key": "starting_capital", "title": "Připraven na start", "desc": "Nastav si počáteční kapitál v nastavení profilu.",
     "points": 10, "target": 1, "stat": "has_capital"},
    {"key": "friends_3", "title": "Parta se sejde", "desc": "Přidej si 3 kamarády.",
     "points": 30, "target": 3, "stat": "friends"},
    {"key": "friends_10", "title": "Sociální motýl", "desc": "Přidej si 10 kamarádů.",
     "points": 100, "target": 10, "stat": "friends"},
    {"key": "first_post", "title": "První příspěvek", "desc": "Napiš první příspěvek na feed.",
     "points": 20, "target": 1, "stat": "posts"},
    {"key": "posts_10", "title": "Influencer", "desc": "Napiš celkem 10 příspěvků na feed.",
     "points": 80, "target": 10, "stat": "posts"},
    {"key": "messages_10", "title": "Ukecaný", "desc": "Pošli celkem 10 zpráv.",
     "points": 20, "target": 10, "stat": "messages"},
    {"key": "calendar_event", "title": "Organizovaný", "desc": "Vytvoř první událost v kalendáři.",
     "points": 15, "target": 1, "stat": "calendar_events"},
    {"key": "calendar_invite", "title": "Týmový hráč", "desc": "Pozvi kamaráda do kalendářové události.",
     "points": 25, "target": 1, "stat": "calendar_invites_sent"},
]

SHOP_ITEMS = [
    {"key": "badge_rocket", "name": "Rocket", "emoji": "🚀", "desc": "Odznak k tvému jménu na profilu.", "cost": 50, "kind": "badge"},
    {"key": "badge_fire", "name": "On Fire", "emoji": "🔥", "desc": "Pro ty na winning streaku.", "cost": 60, "kind": "badge"},
    {"key": "badge_bull", "name": "Bull", "emoji": "🐂", "desc": "Věčný optimista.", "cost": 80, "kind": "badge"},
    {"key": "badge_bear", "name": "Bear", "emoji": "🐻", "desc": "Věčný pesimista.", "cost": 80, "kind": "badge"},
    {"key": "badge_diamond", "name": "Diamond Hands", "emoji": "💎", "desc": "Nikdy neprodává se ztrátou (aspoň psychicky).", "cost": 100, "kind": "badge"},
    {"key": "badge_shark", "name": "Shark", "emoji": "🦈", "desc": "Loví příležitosti na trhu.", "cost": 100, "kind": "badge"},
    {"key": "badge_crown", "name": "King", "emoji": "👑", "desc": "Protože si to zasloužíš.", "cost": 250, "kind": "badge"},
]


def _compute_stats(user_id):
    trades_row = query_one("SELECT COUNT(*) AS c FROM trades WHERE user_id=?", (user_id,))
    trades = trades_row["c"] if trades_row else 0

    wins_row = query_one("SELECT COUNT(*) AS c FROM trades WHERE user_id=? AND profit_loss > 0", (user_id,))
    wins = wins_row["c"] if wins_row else 0
    winrate = round((wins / trades) * 100, 1) if trades else 0

    friends_row = query_one(
        """SELECT COUNT(*) AS c FROM friendships
           WHERE status='accepted' AND (requester_id=? OR addressee_id=?)""",
        (user_id, user_id),
    )
    friends = friends_row["c"] if friends_row else 0

    posts_row = query_one("SELECT COUNT(*) AS c FROM posts WHERE user_id=?", (user_id,))
    posts = posts_row["c"] if posts_row else 0

    messages_row = query_one("SELECT COUNT(*) AS c FROM messages WHERE sender_id=?", (user_id,))
    messages_sent = messages_row["c"] if messages_row else 0

    events_row = query_one("SELECT COUNT(*) AS c FROM calendar_events WHERE user_id=?", (user_id,))
    calendar_events = events_row["c"] if events_row else 0

    invites_row = query_one("SELECT COUNT(*) AS c FROM calendar_invites WHERE inviter_id=?", (user_id,))
    calendar_invites_sent = invites_row["c"] if invites_row else 0

    user = query_one("SELECT starting_capital FROM users WHERE id=?", (user_id,))
    has_capital = 1 if user and user["starting_capital"] else 0

    return {
        "trades": trades, "winrate": winrate, "friends": friends, "posts": posts,
        "messages": messages_sent, "calendar_events": calendar_events,
        "calendar_invites_sent": calendar_invites_sent, "has_capital": has_capital,
    }


def _progress_value(stats, ch):
    if ch["stat"] == "winrate" and stats.get("trades", 0) < ch.get("min_trades", 0):
        return 0
    return stats.get(ch["stat"], 0)


def get_user_points(user_id):
    row = query_one("SELECT points FROM users WHERE id=?", (user_id,))
    return (row["points"] or 0) if row else 0


def get_user_badges(user_id):
    """Vrati seznam odznaku (emoji + nazev), ktere si uzivatel koupil - pro zobrazeni na profilu."""
    owned_keys = {r["item_key"] for r in query_all("SELECT item_key FROM shop_purchases WHERE user_id=?", (user_id,))}
    return [it for it in SHOP_ITEMS if it["kind"] == "badge" and it["key"] in owned_keys]


@bp.route("/challenges")
@login_required
def list_challenges():
    stats = _compute_stats(g.user["id"])
    claimed_keys = {
        r["challenge_key"] for r in query_all(
            "SELECT challenge_key FROM challenge_claims WHERE user_id=?", (g.user["id"],)
        )
    }
    items = []
    for ch in CHALLENGES:
        progress = _progress_value(stats, ch)
        items.append({
            **ch,
            "progress": min(progress, ch["target"]),
            "complete": progress >= ch["target"],
            "claimed": ch["key"] in claimed_keys,
        })
    return render_template("challenges/list.html", challenges=items, points=get_user_points(g.user["id"]))


@bp.route("/challenges/<key>/claim", methods=["POST"])
@login_required
def claim_challenge(key):
    ch = next((c for c in CHALLENGES if c["key"] == key), None)
    if not ch:
        flash("Neznámá výzva.", "error")
        return redirect(url_for("challenges_bp.list_challenges"))

    already = query_one(
        "SELECT 1 FROM challenge_claims WHERE user_id=? AND challenge_key=?", (g.user["id"], key)
    )
    if already:
        flash("Tuhle výzvu už jsi vyzvedl/a dřív.", "error")
        return redirect(url_for("challenges_bp.list_challenges"))

    stats = _compute_stats(g.user["id"])
    if _progress_value(stats, ch) < ch["target"]:
        flash("Tahle výzva ještě není splněná.", "error")
        return redirect(url_for("challenges_bp.list_challenges"))

    execute(
        "INSERT INTO challenge_claims (user_id, challenge_key, points_awarded) VALUES (?,?,?)",
        (g.user["id"], key, ch["points"]),
    )
    execute("UPDATE users SET points = COALESCE(points,0) + ? WHERE id=?", (ch["points"], g.user["id"]))
    flash(f"Splněno! Získáváš {ch['points']} bodů.", "success")
    return redirect(url_for("challenges_bp.list_challenges"))


@bp.route("/shop")
@login_required
def shop():
    owned_keys = {r["item_key"] for r in query_all("SELECT item_key FROM shop_purchases WHERE user_id=?", (g.user["id"],))}
    items = [{**it, "owned": it["key"] in owned_keys} for it in SHOP_ITEMS]
    return render_template("shop/view.html", items=items, points=get_user_points(g.user["id"]))


@bp.route("/shop/<key>/buy", methods=["POST"])
@login_required
def buy_item(key):
    item = next((i for i in SHOP_ITEMS if i["key"] == key), None)
    if not item:
        flash("Neznámá položka.", "error")
        return redirect(url_for("challenges_bp.shop"))

    owned = query_one("SELECT 1 FROM shop_purchases WHERE user_id=? AND item_key=?", (g.user["id"], key))
    if owned:
        flash("Tohle už vlastníš.", "error")
        return redirect(url_for("challenges_bp.shop"))

    points = get_user_points(g.user["id"])
    if points < item["cost"]:
        flash(f"Nemáš dost bodů (potřebuješ {item['cost']}, máš {points}).", "error")
        return redirect(url_for("challenges_bp.shop"))

    execute("UPDATE users SET points = points - ? WHERE id=?", (item["cost"], g.user["id"]))
    execute(
        "INSERT INTO shop_purchases (user_id, item_key, cost_paid) VALUES (?,?,?)",
        (g.user["id"], key, item["cost"]),
    )
    flash(f"Koupeno: {item['emoji']} {item['name']}!", "success")
    return redirect(url_for("challenges_bp.shop"))
