import os
import uuid
from datetime import datetime, timedelta
from functools import wraps

from flask import session, g, redirect, url_for, request, flash, current_app
from werkzeug.utils import secure_filename

from db import query_one, execute, query_all

ALLOWED_IMAGE_EXT = {"png", "jpg", "jpeg", "gif", "webp"}
ALLOWED_DATA_EXT = {"csv", "htm", "html"}


def load_logged_in_user():
    user_id = session.get("user_id")
    if user_id is None:
        g.user = None
    else:
        g.user = query_one("SELECT * FROM users WHERE id = ?", (user_id,))
        if g.user and g.user["is_banned"]:
            session.clear()
            g.user = None


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if g.user is None:
            flash("Nejdriv se prosim prihlas.", "error")
            return redirect(url_for("auth.login", next=request.path))
        return view(*args, **kwargs)
    return wrapped


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if g.user is None:
            flash("Nejdriv se prosim prihlas.", "error")
            return redirect(url_for("auth.login", next=request.path))
        if not g.user["is_admin"]:
            flash("Na tuhle stránku nemáš oprávnění.", "error")
            return redirect(url_for("social.feed"))
        return view(*args, **kwargs)
    return wrapped


def current_user():
    return g.user


def allowed_file(filename, allowed_set):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in allowed_set


def save_upload(file_storage, subfolder):
    """Ulozi nahrany soubor do static/uploads/<subfolder>/ a vrati relativni cestu, nebo None."""
    if not file_storage or file_storage.filename == "":
        return None
    filename = secure_filename(file_storage.filename)
    if not allowed_file(filename, ALLOWED_IMAGE_EXT):
        return None
    ext = filename.rsplit(".", 1)[1].lower()
    unique_name = f"{uuid.uuid4().hex}.{ext}"
    target_dir = os.path.join(current_app.static_folder, "uploads", subfolder)
    os.makedirs(target_dir, exist_ok=True)
    path = os.path.join(target_dir, unique_name)
    file_storage.save(path)
    return f"uploads/{subfolder}/{unique_name}"


def friendship_between(user_a_id, user_b_id):
    return query_one(
        """SELECT * FROM friendships
           WHERE (requester_id = ? AND addressee_id = ?)
              OR (requester_id = ? AND addressee_id = ?)""",
        (user_a_id, user_b_id, user_b_id, user_a_id),
    )


def are_friends(user_a_id, user_b_id):
    f = friendship_between(user_a_id, user_b_id)
    return bool(f and f["status"] == "accepted")


def is_blocked(user_a_id, user_b_id):
    f = friendship_between(user_a_id, user_b_id)
    return bool(f and f["status"] == "blocked")


def friend_ids(user_id):
    rows = query_all(
        """SELECT CASE WHEN requester_id = ? THEN addressee_id ELSE requester_id END AS fid
           FROM friendships WHERE status='accepted' AND (requester_id = ? OR addressee_id = ?)""",
        (user_id, user_id, user_id),
    )
    return [r["fid"] for r in rows]


def notify(user_id, ntype, actor_id=None, target_id=None, message=""):
    if user_id == actor_id:
        return
    settings = query_one("SELECT * FROM user_settings WHERE user_id = ?", (user_id,))
    if settings:
        if ntype == "message" and not settings["notify_messages"]:
            return
        if ntype in ("friend_request", "friend_accept", "like", "comment") and not settings["notify_social"]:
            return
    execute(
        "INSERT INTO notifications (user_id, type, actor_id, target_id, message) VALUES (?,?,?,?,?)",
        (user_id, ntype, actor_id, target_id, message),
    )


def unread_notification_count(user_id):
    row = query_one(
        "SELECT COUNT(*) AS c FROM notifications WHERE user_id = ? AND is_read = 0", (user_id,)
    )
    return row["c"] if row else 0


def unread_message_count(user_id):
    row = query_one(
        "SELECT COUNT(*) AS c FROM messages WHERE recipient_id = ? AND read_at IS NULL", (user_id,)
    )
    return row["c"] if row else 0


def comments_for_posts(post_ids):
    if not post_ids:
        return {}
    placeholders = ",".join("?" * len(post_ids))
    rows = query_all(
        f"""SELECT comments.*, users.username, users.display_name, users.is_admin
            FROM comments JOIN users ON users.id = comments.user_id
            WHERE post_id IN ({placeholders}) ORDER BY comments.created_at ASC""",
        post_ids,
    )
    result = {}
    for r in rows:
        result.setdefault(r["post_id"], []).append(r)
    return result


def week_start_for(date_obj):
    """Vrati datum pondeli tydne (jako date), pro dany datetime/date."""
    d = date_obj.date() if hasattr(date_obj, "date") else date_obj
    return d - timedelta(days=d.weekday())


def parse_dt(value):
    """Zkusi naparsovat ruzne formaty data/casu z formulare nebo MT4 exportu."""
    if not value:
        return None
    value = str(value).strip()
    formats = [
        "%Y-%m-%dT%H:%M",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d",
        "%Y.%m.%d %H:%M:%S",
        "%Y.%m.%d %H:%M",
        "%d.%m.%Y %H:%M",
        "%d.%m.%Y",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return None


def fmt_dt(value, pattern="%d.%m.%Y %H:%M"):
    if not value:
        return ""
    if isinstance(value, str):
        dt = parse_dt(value)
        if not dt:
            return value
    else:
        dt = value
    return dt.strftime(pattern)
