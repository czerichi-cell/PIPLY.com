from flask import Blueprint, render_template, request, redirect, url_for, flash, g

from db import query_one, query_all, execute
from helpers import login_required

bp = Blueprint("challenges_bp", __name__)


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
    if ch["stat"] == "winrate" and stats.get("trades", 0) < (ch["min_trades"] or 0):
        return 0
    return stats.get(ch["stat"], 0)


def get_user_points(user_id):
    row = query_one("SELECT points FROM users WHERE id=?", (user_id,))
    return (row["points"] or 0) if row else 0


def get_user_badges(user_id):
    """Vrati seznam odznaku, ktere si uzivatel koupil - pro zobrazeni na profilu."""
    return query_all(
        """SELECT shop_items.* FROM shop_purchases
           JOIN shop_items ON shop_items.item_key = shop_purchases.item_key
           WHERE shop_purchases.user_id = ? AND shop_items.kind = 'badge'
           ORDER BY shop_purchases.purchased_at""",
        (user_id,),
    )


def get_user_owned_banners(user_id):
    """Vrati seznam bannery, ktere si uzivatel koupil v obchode (kromě vlastniho uploadu)."""
    return query_all(
        """SELECT shop_items.* FROM shop_purchases
           JOIN shop_items ON shop_items.item_key = shop_purchases.item_key
           WHERE shop_purchases.user_id = ? AND shop_items.kind = 'banner'
           ORDER BY shop_purchases.purchased_at""",
        (user_id,),
    )


@bp.route("/challenges")
@login_required
def list_challenges():
    stats = _compute_stats(g.user["id"])
    all_challenges = query_all("SELECT * FROM challenges WHERE is_active=1 ORDER BY points")
    claimed_keys = {
        r["challenge_key"] for r in query_all(
            "SELECT challenge_key FROM challenge_claims WHERE user_id=?", (g.user["id"],)
        )
    }
    items = []
    for ch in all_challenges:
        progress = _progress_value(stats, ch)
        items.append({
            "key": ch["challenge_key"], "title": ch["title"], "desc": ch["description"],
            "points": ch["points"], "target": ch["target"], "stat": ch["stat"],
            "progress": min(progress, ch["target"]),
            "complete": progress >= ch["target"],
            "claimed": ch["challenge_key"] in claimed_keys,
        })
    return render_template("challenges/list.html", challenges=items, points=get_user_points(g.user["id"]))


@bp.route("/challenges/<key>/claim", methods=["POST"])
@login_required
def claim_challenge(key):
    ch = query_one("SELECT * FROM challenges WHERE challenge_key=? AND is_active=1", (key,))
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
    all_items = query_all("SELECT * FROM shop_items WHERE is_active=1 ORDER BY kind, cost")
    owned_keys = {r["item_key"] for r in query_all("SELECT item_key FROM shop_purchases WHERE user_id=?", (g.user["id"],))}
    badges = [dict(it, owned=it["item_key"] in owned_keys) for it in all_items if it["kind"] == "badge"]
    banners = [dict(it, owned=it["item_key"] in owned_keys) for it in all_items if it["kind"] == "banner"]
    return render_template("shop/view.html", badges=badges, banners=banners, points=get_user_points(g.user["id"]))


@bp.route("/shop/<key>/buy", methods=["POST"])
@login_required
def buy_item(key):
    item = query_one("SELECT * FROM shop_items WHERE item_key=? AND is_active=1", (key,))
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
    flash(f"Koupeno: {item['emoji'] or ''} {item['name']}!", "success")
    return redirect(url_for("challenges_bp.shop"))
