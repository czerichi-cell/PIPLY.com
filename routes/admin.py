from flask import Blueprint, render_template, request, redirect, url_for, flash, g

from db import query_one, query_all, execute
from helpers import admin_required, save_upload

bp = Blueprint("admin_bp", __name__, url_prefix="/admin")


@bp.route("")
@admin_required
def dashboard():
    stats = {
        "users": query_one("SELECT COUNT(*) AS c FROM users")["c"],
        "posts": query_one("SELECT COUNT(*) AS c FROM posts")["c"],
        "trades": query_one("SELECT COUNT(*) AS c FROM trades")["c"],
        "messages": query_one("SELECT COUNT(*) AS c FROM messages")["c"],
    }
    q = request.args.get("q", "").strip()
    if q:
        users = query_all(
            "SELECT * FROM users WHERE username LIKE ? OR display_name LIKE ? OR email LIKE ? ORDER BY created_at DESC",
            (f"%{q}%", f"%{q}%", f"%{q}%"),
        )
    else:
        users = query_all("SELECT * FROM users ORDER BY created_at DESC LIMIT 100")
    recent_posts = query_all(
        """SELECT posts.*, users.username, users.display_name
           FROM posts JOIN users ON users.id = posts.user_id
           ORDER BY posts.created_at DESC LIMIT 30"""
    )
    return render_template("admin/dashboard.html", stats=stats, users=users, recent_posts=recent_posts, q=q)


@bp.route("/user/<int:user_id>/toggle-ban", methods=["POST"])
@admin_required
def toggle_ban(user_id):
    if user_id == g.user["id"]:
        flash("Sám sebe banovat nemůžeš.", "error")
        return redirect(url_for("admin_bp.dashboard"))
    target = query_one("SELECT * FROM users WHERE id=?", (user_id,))
    if not target:
        flash("Uživatel neexistuje.", "error")
        return redirect(url_for("admin_bp.dashboard"))
    if target["is_admin"] and not target["is_banned"]:
        flash("Nejdřív musíš uživateli odebrat admin práva, než ho můžeš zabanovat.", "error")
        return redirect(url_for("admin_bp.dashboard"))
    execute("UPDATE users SET is_banned = 1 - is_banned WHERE id=?", (user_id,))
    verb = "odbanován" if target["is_banned"] else "zabanován"
    flash(f"Uživatel {target['display_name'] or target['username']} byl {verb}.", "success")
    return redirect(url_for("admin_bp.dashboard"))


@bp.route("/user/<int:user_id>/delete", methods=["POST"])
@admin_required
def delete_user(user_id):
    if user_id == g.user["id"]:
        flash("Sám svůj účet takhle smazat nemůžeš.", "error")
        return redirect(url_for("admin_bp.dashboard"))
    target = query_one("SELECT * FROM users WHERE id=?", (user_id,))
    if not target:
        flash("Uživatel neexistuje.", "error")
        return redirect(url_for("admin_bp.dashboard"))
    execute("DELETE FROM users WHERE id=?", (user_id,))
    flash(f"Účet {target['display_name'] or target['username']} byl trvale smazán.", "success")
    return redirect(url_for("admin_bp.dashboard"))


@bp.route("/user/<int:user_id>/toggle-admin", methods=["POST"])
@admin_required
def toggle_admin(user_id):
    if user_id == g.user["id"]:
        flash("Nemůžeš si sám sobě odebrat admin práva odsud – požádej jiného admina.", "error")
        return redirect(url_for("admin_bp.dashboard"))
    target = query_one("SELECT * FROM users WHERE id=?", (user_id,))
    if not target:
        flash("Uživatel neexistuje.", "error")
        return redirect(url_for("admin_bp.dashboard"))
    execute("UPDATE users SET is_admin = 1 - is_admin WHERE id=?", (user_id,))
    verb = "odebrána" if target["is_admin"] else "udělena"
    flash(f"Admin práva pro {target['display_name'] or target['username']} {verb}.", "success")
    return redirect(url_for("admin_bp.dashboard"))


@bp.route("/post/<int:post_id>/delete", methods=["POST"])
@admin_required
def delete_post(post_id):
    execute("DELETE FROM posts WHERE id=?", (post_id,))
    flash("Příspěvek smazán.", "success")
    return redirect(url_for("admin_bp.dashboard"))


@bp.route("/shop-items")
@admin_required
def shop_items():
    items = query_all("SELECT * FROM shop_items ORDER BY kind, cost")
    return render_template("admin/shop_items.html", items=items)


@bp.route("/shop-items/new", methods=["POST"])
@admin_required
def new_shop_item():
    item_key = request.form.get("item_key", "").strip().lower().replace(" ", "_")
    kind = request.form.get("kind", "badge")
    name = request.form.get("name", "").strip()
    description = request.form.get("description", "").strip()
    emoji = request.form.get("emoji", "").strip()
    cost = request.form.get("cost", "0").strip()

    if not item_key or not name or not cost.isdigit():
        flash("Vyplň prosím klíč, název a platnou cenu (celé číslo).", "error")
        return redirect(url_for("admin_bp.shop_items"))

    existing = query_one("SELECT 1 FROM shop_items WHERE item_key=?", (item_key,))
    if existing:
        flash("Položka s tímhle klíčem už existuje – zvol jiný.", "error")
        return redirect(url_for("admin_bp.shop_items"))

    image_file = request.files.get("image")
    image_path = save_upload(image_file, "shop") if image_file and image_file.filename else None

    if kind not in ("badge", "banner"):
        kind = "badge"

    execute(
        """INSERT INTO shop_items (item_key, kind, name, description, emoji, image_path, cost)
           VALUES (?,?,?,?,?,?,?)""",
        (item_key, kind, name, description, emoji or None, image_path, int(cost)),
    )
    flash(f"Položka „{name}“ přidána do obchodu.", "success")
    return redirect(url_for("admin_bp.shop_items"))


@bp.route("/shop-items/<int:item_id>/toggle-active", methods=["POST"])
@admin_required
def toggle_shop_item(item_id):
    execute("UPDATE shop_items SET is_active = 1 - is_active WHERE id=?", (item_id,))
    return redirect(url_for("admin_bp.shop_items"))


@bp.route("/shop-items/<int:item_id>/delete", methods=["POST"])
@admin_required
def delete_shop_item(item_id):
    execute("DELETE FROM shop_items WHERE id=?", (item_id,))
    flash("Položka smazána z obchodu (uživatelé, co ji už vlastní, o ni nepřijdou).", "success")
    return redirect(url_for("admin_bp.shop_items"))


CHALLENGE_STATS = [
    ("trades", "Počet obchodů v deníku"),
    ("winrate", "Winrate v % (vyžaduje min. obchodů)"),
    ("has_capital", "Nastavený počáteční kapitál (0/1)"),
    ("friends", "Počet přátel"),
    ("posts", "Počet příspěvků na feedu"),
    ("messages", "Počet odeslaných zpráv"),
    ("calendar_events", "Počet událostí v kalendáři"),
    ("calendar_invites_sent", "Počet odeslaných pozvánek do kalendáře"),
]


@bp.route("/challenges")
@admin_required
def challenges_admin():
    items = query_all("SELECT * FROM challenges ORDER BY points")
    return render_template("admin/challenges.html", items=items, stat_options=CHALLENGE_STATS)


@bp.route("/challenges/new", methods=["POST"])
@admin_required
def new_challenge():
    key = request.form.get("challenge_key", "").strip().lower().replace(" ", "_")
    title = request.form.get("title", "").strip()
    description = request.form.get("description", "").strip()
    points = request.form.get("points", "0").strip()
    target = request.form.get("target", "1").strip()
    stat = request.form.get("stat", "trades")
    min_trades = request.form.get("min_trades", "0").strip() or "0"

    if not key or not title or not points.isdigit() or not target.isdigit() or not min_trades.isdigit():
        flash("Vyplň prosím klíč, název a platná čísla pro body/cíl.", "error")
        return redirect(url_for("admin_bp.challenges_admin"))

    if query_one("SELECT 1 FROM challenges WHERE challenge_key=?", (key,)):
        flash("Výzva s tímhle klíčem už existuje – zvol jiný.", "error")
        return redirect(url_for("admin_bp.challenges_admin"))

    execute(
        """INSERT INTO challenges (challenge_key, title, description, points, target, stat, min_trades)
           VALUES (?,?,?,?,?,?,?)""",
        (key, title, description, int(points), int(target), stat, int(min_trades)),
    )
    flash(f"Výzva „{title}“ přidána.", "success")
    return redirect(url_for("admin_bp.challenges_admin"))


@bp.route("/challenges/<int:challenge_id>/toggle-active", methods=["POST"])
@admin_required
def toggle_challenge(challenge_id):
    execute("UPDATE challenges SET is_active = 1 - is_active WHERE id=?", (challenge_id,))
    return redirect(url_for("admin_bp.challenges_admin"))


@bp.route("/challenges/<int:challenge_id>/delete", methods=["POST"])
@admin_required
def delete_challenge(challenge_id):
    ch = query_one("SELECT * FROM challenges WHERE id=?", (challenge_id,))
    if ch:
        execute("DELETE FROM challenge_claims WHERE challenge_key=?", (ch["challenge_key"],))
        execute("DELETE FROM challenges WHERE id=?", (challenge_id,))
        flash(f"Výzva „{ch['title']}“ smazána (včetně záznamů o jejím vyzvednutí).", "success")
    return redirect(url_for("admin_bp.challenges_admin"))
