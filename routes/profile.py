from flask import Blueprint, render_template, request, redirect, url_for, flash, g

from db import query_one, query_all, execute
from helpers import (
    login_required, save_upload, friendship_between, are_friends, friend_ids,
    comments_for_posts,
)

bp = Blueprint("profile", __name__, url_prefix="/u")


def _trade_stats_summary(user_id):
    row = query_one(
        """SELECT COUNT(*) AS n,
                  COALESCE(SUM(profit_loss),0) AS total_pl,
                  COALESCE(SUM(CASE WHEN profit_loss > 0 THEN 1 ELSE 0 END),0) AS wins
           FROM trades WHERE user_id = ?""",
        (user_id,),
    )
    winrate = round(100 * row["wins"] / row["n"], 1) if row["n"] else 0
    return {"count": row["n"], "total_pl": row["total_pl"], "winrate": winrate}


@bp.route("/<username>")
@login_required
def view_profile(username):
    profile_user = query_one("SELECT * FROM users WHERE username = ?", (username,))
    if profile_user is None:
        flash("Uživatel neexistuje.", "error")
        return redirect(url_for("social.feed"))

    me = g.user["id"]
    them = profile_user["id"]
    is_me = me == them
    friendship = friendship_between(me, them) if not is_me else None
    friend_status = friendship["status"] if friendship else None
    friend_req_from_me = bool(friendship and friendship["requester_id"] == me)

    # viditelnost prispevku: verejne vsem, friends jen pratelum/mne, only_me jen mne
    if is_me:
        visibility_clause = "1=1"
    elif are_friends(me, them):
        visibility_clause = "visibility IN ('public','friends')"
    else:
        visibility_clause = "visibility = 'public'"

    posts = query_all(
        f"""SELECT posts.*, users.username, users.display_name, users.avatar_path, users.is_admin,
                   (SELECT COUNT(*) FROM likes WHERE likes.post_id = posts.id) AS like_count,
                   (SELECT COUNT(*) FROM comments WHERE comments.post_id = posts.id) AS comment_count,
                   (SELECT COUNT(*) FROM likes WHERE likes.post_id = posts.id AND likes.user_id = ?) AS liked_by_me
            FROM posts JOIN users ON users.id = posts.user_id
            WHERE posts.user_id = ? AND {visibility_clause}
            ORDER BY posts.created_at DESC LIMIT 30""",
        (me, them),
    )

    post_comments = comments_for_posts([p["id"] for p in posts])
    stats = _trade_stats_summary(them)
    friends_count = len(friend_ids(them))
    recent_trades = []
    if is_me or are_friends(me, them):
        recent_trades = query_all(
            "SELECT * FROM trades WHERE user_id = ? ORDER BY COALESCE(closed_at, opened_at) DESC LIMIT 5",
            (them,),
        )

    from routes.challenges import get_user_badges
    badges = get_user_badges(them)

    banner_url = None
    if profile_user["banner_path"]:
        banner_url = url_for("static", filename=profile_user["banner_path"])
    elif profile_user["selected_banner_key"]:
        banner_item = query_one("SELECT * FROM shop_items WHERE item_key=?", (profile_user["selected_banner_key"],))
        if banner_item and banner_item["image_path"]:
            banner_url = url_for("static", filename=banner_item["image_path"])

    return render_template(
        "profile/view.html",
        profile_user=profile_user,
        is_me=is_me,
        friend_status=friend_status,
        friend_req_from_me=friend_req_from_me,
        friendship_id=friendship["id"] if friendship else None,
        posts=posts,
        post_comments=post_comments,
        stats=stats,
        friends_count=friends_count,
        recent_trades=recent_trades,
        badges=badges,
        banner_url=banner_url,
    )


@bp.route("/settings/edit", methods=["GET", "POST"])
@login_required
def edit_profile():
    if request.method == "POST":
        display_name = request.form.get("display_name", "").strip() or g.user["username"]
        bio = request.form.get("bio", "").strip()
        starting_capital = request.form.get("starting_capital", "0").strip() or "0"
        try:
            starting_capital = float(starting_capital.replace(",", "."))
        except ValueError:
            starting_capital = 0

        avatar_path = g.user["avatar_path"]
        file = request.files.get("avatar")
        saved = save_upload(file, "avatars")
        if saved:
            avatar_path = saved
        avatar_position = request.form.get("avatar_position", "").strip() or g.user["avatar_position"] or "50% 50%"

        banner_path = g.user["banner_path"]
        selected_banner_key = g.user["selected_banner_key"]
        banner_file = request.files.get("banner")
        banner_saved = save_upload(banner_file, "banners")
        chosen_banner_key = request.form.get("banner_key", "").strip()
        if banner_saved:
            banner_path = banner_saved
            selected_banner_key = None
        elif chosen_banner_key:
            if chosen_banner_key == "__none__":
                banner_path = None
                selected_banner_key = None
            else:
                selected_banner_key = chosen_banner_key
                banner_path = None
        banner_position = request.form.get("banner_position", "").strip() or g.user["banner_position"] or "50% 50%"

        execute(
            """UPDATE users SET display_name=?, bio=?, avatar_path=?, starting_capital=?,
               banner_path=?, selected_banner_key=?, avatar_position=?, banner_position=? WHERE id=?""",
            (display_name, bio, avatar_path, starting_capital, banner_path, selected_banner_key,
             avatar_position, banner_position, g.user["id"]),
        )
        flash("Profil uložen.", "success")
        return redirect(url_for("profile.view_profile", username=g.user["username"]))

    from routes.challenges import get_user_owned_banners
    settings = query_one("SELECT * FROM user_settings WHERE user_id = ?", (g.user["id"],))
    owned_banners = get_user_owned_banners(g.user["id"])

    banner_url = None
    if g.user["banner_path"]:
        banner_url = url_for("static", filename=g.user["banner_path"])
    elif g.user["selected_banner_key"]:
        banner_item = query_one("SELECT * FROM shop_items WHERE item_key=?", (g.user["selected_banner_key"],))
        if banner_item and banner_item["image_path"]:
            banner_url = url_for("static", filename=banner_item["image_path"])

    return render_template("profile/edit.html", settings=settings, owned_banners=owned_banners, banner_url=banner_url)


@bp.route("/settings/privacy", methods=["POST"])
@login_required
def update_privacy():
    messages_privacy = request.form.get("messages_privacy", "friends")
    notify_messages = 1 if request.form.get("notify_messages") else 0
    notify_social = 1 if request.form.get("notify_social") else 0
    chat_widget_enabled = 1 if request.form.get("chat_widget_enabled") else 0
    notify_sound_enabled = 1 if request.form.get("notify_sound_enabled") else 0
    execute(
        """UPDATE user_settings SET messages_privacy=?, notify_messages=?, notify_social=?,
           chat_widget_enabled=?, notify_sound_enabled=? WHERE user_id=?""",
        (messages_privacy, notify_messages, notify_social, chat_widget_enabled, notify_sound_enabled, g.user["id"]),
    )
    flash("Nastavení uloženo.", "success")
    return redirect(url_for("profile.edit_profile"))


@bp.route("/search")
@login_required
def search_users():
    q = request.args.get("q", "").strip()
    results = []
    if q:
        results = query_all(
            """SELECT * FROM users WHERE (username LIKE ? OR display_name LIKE ?) AND id != ?
               LIMIT 20""",
            (f"%{q}%", f"%{q}%", g.user["id"]),
        )
    return render_template("profile/search.html", results=results, q=q)


@bp.route("/tutorial/complete", methods=["POST"])
@login_required
def complete_tutorial():
    execute("UPDATE users SET has_seen_tutorial=1 WHERE id=?", (g.user["id"],))
    return {"ok": True}


@bp.route("/tutorial/restart", methods=["POST"])
@login_required
def restart_tutorial():
    """Umoznuje znovu spustit tutorial rucne (napr. z odkazu v nastaveni)."""
    execute("UPDATE users SET has_seen_tutorial=0 WHERE id=?", (g.user["id"],))
    return redirect(url_for("social.feed"))