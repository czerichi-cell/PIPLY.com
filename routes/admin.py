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
    users = query_all("SELECT * FROM users ORDER BY created_at DESC")
    recent_posts = query_all(
        """SELECT posts.*, users.username, users.display_name
           FROM posts JOIN users ON users.id = posts.user_id
           ORDER BY posts.created_at DESC LIMIT 30"""
    )
    return render_template("admin/dashboard.html", stats=stats, users=users, recent_posts=recent_posts)


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
