from flask import Blueprint, render_template, redirect, url_for, g

from db import query_all, execute
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
    execute("UPDATE notifications SET is_read=1 WHERE user_id=?", (g.user["id"],))
    return render_template("notifications/list.html", notes=notes)
