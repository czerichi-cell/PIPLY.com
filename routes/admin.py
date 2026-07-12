from flask import Blueprint, render_template, request, redirect, url_for, flash, g

from db import query_one, query_all, execute
from helpers import admin_required

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
