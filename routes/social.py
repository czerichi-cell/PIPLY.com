from flask import Blueprint, render_template, request, redirect, url_for, flash, g, jsonify

from db import query_one, query_all, execute
from helpers import (
    login_required, save_upload, friend_ids, friendship_between, are_friends,
    notify, comments_for_posts,
)

bp = Blueprint("social", __name__)


def _visible_posts_sql(me, fids, after_id=None):
    placeholders = ",".join("?" * len(fids))
    sql = f"""SELECT posts.*, users.username, users.display_name, users.avatar_path,
                   (SELECT COUNT(*) FROM likes WHERE likes.post_id = posts.id) AS like_count,
                   (SELECT COUNT(*) FROM comments WHERE comments.post_id = posts.id) AS comment_count,
                   (SELECT COUNT(*) FROM likes WHERE likes.post_id = posts.id AND likes.user_id = ?) AS liked_by_me
            FROM posts JOIN users ON users.id = posts.user_id
            WHERE (
                (posts.user_id IN ({placeholders}) AND posts.visibility IN ('public','friends'))
                OR posts.visibility = 'public'
                OR (posts.user_id = ? AND posts.visibility = 'only_me')
            )"""
    params = [me] + fids + [me]
    if after_id is not None:
        sql += " AND posts.id > ?"
        params.append(after_id)
    sql += " GROUP BY posts.id ORDER BY posts.created_at DESC LIMIT 50"
    return sql, params


@bp.route("/feed")
@login_required
def feed():
    me = g.user["id"]
    fids = friend_ids(me) + [me]
    sql, params = _visible_posts_sql(me, fids)
    posts = query_all(sql, params)
    post_comments = comments_for_posts([p["id"] for p in posts])
    latest_id = posts[0]["id"] if posts else 0
    return render_template("social/feed.html", posts=posts, post_comments=post_comments, latest_id=latest_id)


@bp.route("/feed/poll")
@login_required
def feed_poll():
    me = g.user["id"]
    after_id = request.args.get("after_id", 0, type=int)
    fids = friend_ids(me) + [me]
    sql, params = _visible_posts_sql(me, fids, after_id=after_id)
    posts = query_all(sql, params)
    if not posts:
        return jsonify({"count": 0, "html": "", "latest_id": after_id})

    post_comments = comments_for_posts([p["id"] for p in posts])
    # posts jsou serazene od nejnovejsiho -> pro spravne poradi pri vlozeni na
    # zacatek feedu je otocime (nejstarsi z nove davky prvni)
    html = "".join(
        render_template("social/_post.html", post=p, post_comments=post_comments)
        for p in reversed(posts)
    )
    return jsonify({"count": len(posts), "html": html, "latest_id": posts[0]["id"]})


@bp.route("/feed/new", methods=["POST"])
@login_required
def new_post():
    content = request.form.get("content", "").strip()
    visibility = request.form.get("visibility", "friends")
    if visibility not in ("public", "friends", "only_me"):
        visibility = "friends"
    image_path = save_upload(request.files.get("image"), "posts")

    if not content and not image_path:
        flash("Napiš aspoň něco, nebo přidej fotku.", "error")
        return redirect(url_for("social.feed"))

    execute(
        "INSERT INTO posts (user_id, content, image_path, visibility) VALUES (?,?,?,?)",
        (g.user["id"], content, image_path, visibility),
    )
    return redirect(url_for("social.feed"))


@bp.route("/post/<int:post_id>/delete", methods=["POST"])
@login_required
def delete_post(post_id):
    execute("DELETE FROM posts WHERE id=? AND user_id=?", (post_id, g.user["id"]))
    flash("Příspěvek smazán.", "success")
    return redirect(request.referrer or url_for("social.feed"))


@bp.route("/post/<int:post_id>/like", methods=["POST"])
@login_required
def like_post(post_id):
    post = query_one("SELECT * FROM posts WHERE id=?", (post_id,))
    if post is None:
        return jsonify({"error": "not found"}), 404

    existing = query_one(
        "SELECT id FROM likes WHERE post_id=? AND user_id=?", (post_id, g.user["id"])
    )
    if existing:
        execute("DELETE FROM likes WHERE id=?", (existing["id"],))
        liked = False
    else:
        execute("INSERT INTO likes (post_id, user_id) VALUES (?,?)", (post_id, g.user["id"]))
        liked = True
        notify(post["user_id"], "like", actor_id=g.user["id"], target_id=post_id,
               message=f"{g.user['display_name'] or g.user['username']} označil(a) tvůj příspěvek jako oblíbený")

    count = query_one("SELECT COUNT(*) AS c FROM likes WHERE post_id=?", (post_id,))["c"]
    return jsonify({"liked": liked, "count": count})


@bp.route("/post/<int:post_id>/comment", methods=["POST"])
@login_required
def comment_post(post_id):
    content = request.form.get("content", "").strip()
    post = query_one("SELECT * FROM posts WHERE id=?", (post_id,))
    if not content or post is None:
        return redirect(request.referrer or url_for("social.feed"))
    execute(
        "INSERT INTO comments (post_id, user_id, content) VALUES (?,?,?)",
        (post_id, g.user["id"], content),
    )
    notify(post["user_id"], "comment", actor_id=g.user["id"], target_id=post_id,
           message=f"{g.user['display_name'] or g.user['username']} okomentoval(a) tvůj příspěvek")
    return redirect(request.referrer or url_for("social.feed"))


# --- Pratele ---------------------------------------------------------

@bp.route("/friends")
@login_required
def friends_list():
    me = g.user["id"]
    accepted = query_all(
        """SELECT users.*, friendships.id AS friendship_id FROM friendships
           JOIN users ON users.id = CASE WHEN friendships.requester_id=? THEN friendships.addressee_id ELSE friendships.requester_id END
           WHERE friendships.status='accepted' AND (friendships.requester_id=? OR friendships.addressee_id=?)""",
        (me, me, me),
    )
    incoming = query_all(
        """SELECT users.*, friendships.id AS friendship_id FROM friendships
           JOIN users ON users.id = friendships.requester_id
           WHERE friendships.addressee_id=? AND friendships.status='pending'""",
        (me,),
    )
    outgoing = query_all(
        """SELECT users.*, friendships.id AS friendship_id FROM friendships
           JOIN users ON users.id = friendships.addressee_id
           WHERE friendships.requester_id=? AND friendships.status='pending'""",
        (me,),
    )
    return render_template(
        "social/friends.html", accepted=accepted, incoming=incoming, outgoing=outgoing
    )


@bp.route("/friends/request/<username>", methods=["POST"])
@login_required
def send_request(username):
    target = query_one("SELECT * FROM users WHERE username=?", (username,))
    if target is None or target["id"] == g.user["id"]:
        flash("Nelze poslat žádost.", "error")
        return redirect(url_for("social.friends_list"))

    existing = friendship_between(g.user["id"], target["id"])
    if existing:
        flash("Se žádostí o přátelství už existuje záznam.", "error")
        return redirect(url_for("profile.view_profile", username=username))

    execute(
        "INSERT INTO friendships (requester_id, addressee_id, status) VALUES (?,?,'pending')",
        (g.user["id"], target["id"]),
    )
    notify(target["id"], "friend_request", actor_id=g.user["id"],
           message=f"{g.user['display_name'] or g.user['username']} ti poslal(a) žádost o přátelství")
    flash("Žádost o přátelství odeslána.", "success")
    return redirect(url_for("profile.view_profile", username=username))


@bp.route("/friends/<int:friendship_id>/accept", methods=["POST"])
@login_required
def accept_request(friendship_id):
    fr = query_one("SELECT * FROM friendships WHERE id=? AND addressee_id=?", (friendship_id, g.user["id"]))
    if fr:
        execute("UPDATE friendships SET status='accepted' WHERE id=?", (friendship_id,))
        notify(fr["requester_id"], "friend_accept", actor_id=g.user["id"],
               message=f"{g.user['display_name'] or g.user['username']} přijal(a) tvou žádost o přátelství")
        flash("Žádost přijata.", "success")
    return redirect(url_for("social.friends_list"))


@bp.route("/friends/<int:friendship_id>/decline", methods=["POST"])
@login_required
def decline_request(friendship_id):
    execute(
        "DELETE FROM friendships WHERE id=? AND (addressee_id=? OR requester_id=?)",
        (friendship_id, g.user["id"], g.user["id"]),
    )
    flash("Žádost odmítnuta / zrušena.", "success")
    return redirect(url_for("social.friends_list"))


@bp.route("/friends/<int:friendship_id>/remove", methods=["POST"])
@login_required
def remove_friend(friendship_id):
    execute(
        "DELETE FROM friendships WHERE id=? AND (addressee_id=? OR requester_id=?) AND status='accepted'",
        (friendship_id, g.user["id"], g.user["id"]),
    )
    flash("Odebráno z přátel.", "success")
    return redirect(url_for("social.friends_list"))


@bp.route("/friends/block/<username>", methods=["POST"])
@login_required
def block_user(username):
    target = query_one("SELECT * FROM users WHERE username=?", (username,))
    if target is None or target["id"] == g.user["id"]:
        return redirect(url_for("social.friends_list"))

    existing = friendship_between(g.user["id"], target["id"])
    if existing:
        execute(
            "UPDATE friendships SET status='blocked', requester_id=?, addressee_id=? WHERE id=?",
            (g.user["id"], target["id"], existing["id"]),
        )
    else:
        execute(
            "INSERT INTO friendships (requester_id, addressee_id, status) VALUES (?,?,'blocked')",
            (g.user["id"], target["id"]),
        )
    flash(f"Uživatel {username} byl zablokován.", "success")
    return redirect(url_for("profile.view_profile", username=username))


@bp.route("/friends/unblock/<username>", methods=["POST"])
@login_required
def unblock_user(username):
    target = query_one("SELECT * FROM users WHERE username=?", (username,))
    if target:
        execute(
            "DELETE FROM friendships WHERE status='blocked' AND requester_id=? AND addressee_id=?",
            (g.user["id"], target["id"]),
        )
        flash(f"Uživatel {username} odblokován.", "success")
    return redirect(url_for("profile.view_profile", username=username))