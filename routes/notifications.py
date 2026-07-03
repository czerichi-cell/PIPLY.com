from flask import Blueprint, render_template, redirect, url_for, flash, g

from db import query_all, query_one, execute
from helpers import login_required

bp = Blueprint("notifications", __name__, url_prefix="/notifications")


@bp.route("")
@login_required
def list_notifications():
    notes = query_all(
        """SELECT notifications.*, users.username AS actor_username,
                  users.display_name AS actor_display_name, users.avatar_path AS actor_avatar
           FROM notifications
           LEFT JOIN users ON users.id = notifications.actor_id
           WHERE notifications.user_id = ?
           ORDER BY notifications.created_at DESC LIMIT 50""",
        (g.user["id"],),
    )
    unread_count = sum(1 for n in notes if not n["is_read"])
    execute("UPDATE notifications SET is_read=1 WHERE user_id=?", (g.user["id"],))
    return render_template("notifications/list.html", notes=notes, unread_count=unread_count)


@bp.route("/<int:notif_id>/delete", methods=["POST"])
@login_required
def delete_notification(notif_id):
    execute("DELETE FROM notifications WHERE id=? AND user_id=?", (notif_id, g.user["id"]))
    flash("Notifikace smazána.", "success")
    return redirect(url_for("notifications.list_notifications"))


@bp.route("/delete-all", methods=["POST"])
@login_required
def delete_all_notifications():
    execute("DELETE FROM notifications WHERE user_id=?", (g.user["id"],))
    flash("Všechny notifikace smazány.", "success")
    return redirect(url_for("notifications.list_notifications"))