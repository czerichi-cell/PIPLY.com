import json
import os
import urllib.parse
import urllib.request

from flask import Blueprint, render_template, request, redirect, url_for, flash, g, jsonify

from db import query_one, query_all, execute
from helpers import login_required, are_friends, is_blocked, notify, save_upload

bp = Blueprint("messages_bp", __name__, url_prefix="/messages")

GIPHY_BASE = "https://api.giphy.com/v1/gifs"


def _giphy_api_key():
    return os.environ.get("GIPHY_API_KEY", "").strip()


def _giphy_request(endpoint, params):
    api_key = _giphy_api_key()
    if not api_key:
        return None, "missing_key"
    params = dict(params)
    params["api_key"] = api_key
    url = f"{GIPHY_BASE}/{endpoint}?{urllib.parse.urlencode(params)}"
    try:
        with urllib.request.urlopen(url, timeout=6) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return data, None
    except Exception as e:
        return None, str(e)


def _message_json(m, me):
    return {
        "id": m["id"],
        "content": m["content"] or "",
        "image_url": url_for("static", filename=m["image_path"]) if m["image_path"] else None,
        "gif_url": m["gif_url"],
        "sender_id": m["sender_id"],
        "created_at": m["created_at"],
        "mine": m["sender_id"] == me,
    }


@bp.route("")
@login_required
def inbox():
    me = g.user["id"]
    conversations = query_all(
        """SELECT u.id, u.username, u.display_name, u.avatar_path,
                  (SELECT content FROM messages m2
                     WHERE (m2.sender_id=u.id AND m2.recipient_id=?) OR (m2.sender_id=? AND m2.recipient_id=u.id)
                     ORDER BY m2.created_at DESC LIMIT 1) AS last_message,
                  (SELECT image_path FROM messages m2b
                     WHERE (m2b.sender_id=u.id AND m2b.recipient_id=?) OR (m2b.sender_id=? AND m2b.recipient_id=u.id)
                     ORDER BY m2b.created_at DESC LIMIT 1) AS last_image,
                  (SELECT gif_url FROM messages m2c
                     WHERE (m2c.sender_id=u.id AND m2c.recipient_id=?) OR (m2c.sender_id=? AND m2c.recipient_id=u.id)
                     ORDER BY m2c.created_at DESC LIMIT 1) AS last_gif,
                  (SELECT created_at FROM messages m3
                     WHERE (m3.sender_id=u.id AND m3.recipient_id=?) OR (m3.sender_id=? AND m3.recipient_id=u.id)
                     ORDER BY m3.created_at DESC LIMIT 1) AS last_at,
                  (SELECT COUNT(*) FROM messages m4 WHERE m4.sender_id=u.id AND m4.recipient_id=? AND m4.read_at IS NULL) AS unread
           FROM users u
           WHERE u.id IN (
               SELECT sender_id FROM messages WHERE recipient_id=?
               UNION
               SELECT recipient_id FROM messages WHERE sender_id=?
           )
           ORDER BY last_at DESC""",
        (me, me, me, me, me, me, me, me, me, me, me),
    )
    return render_template("messages/inbox.html", conversations=conversations)


@bp.route("/fragment")
@login_required
def inbox_fragment():
    """Vraci jen fragment se seznamem konverzaci, pro realtime refresh inboxu bez reloadu."""
    me = g.user["id"]
    conversations = query_all(
        """SELECT u.id, u.username, u.display_name, u.avatar_path,
                  (SELECT content FROM messages m2
                     WHERE (m2.sender_id=u.id AND m2.recipient_id=?) OR (m2.sender_id=? AND m2.recipient_id=u.id)
                     ORDER BY m2.created_at DESC LIMIT 1) AS last_message,
                  (SELECT image_path FROM messages m2b
                     WHERE (m2b.sender_id=u.id AND m2b.recipient_id=?) OR (m2b.sender_id=? AND m2b.recipient_id=u.id)
                     ORDER BY m2b.created_at DESC LIMIT 1) AS last_image,
                  (SELECT gif_url FROM messages m2c
                     WHERE (m2c.sender_id=u.id AND m2c.recipient_id=?) OR (m2c.sender_id=? AND m2c.recipient_id=u.id)
                     ORDER BY m2c.created_at DESC LIMIT 1) AS last_gif,
                  (SELECT created_at FROM messages m3
                     WHERE (m3.sender_id=u.id AND m3.recipient_id=?) OR (m3.sender_id=? AND m3.recipient_id=u.id)
                     ORDER BY m3.created_at DESC LIMIT 1) AS last_at,
                  (SELECT COUNT(*) FROM messages m4 WHERE m4.sender_id=u.id AND m4.recipient_id=? AND m4.read_at IS NULL) AS unread
           FROM users u
           WHERE u.id IN (
               SELECT sender_id FROM messages WHERE recipient_id=?
               UNION
               SELECT recipient_id FROM messages WHERE sender_id=?
           )
           ORDER BY last_at DESC""",
        (me, me, me, me, me, me, me, me, me, me, me),
    )
    return render_template("messages/_conversations.html", conversations=conversations)


@bp.route("/<username>", methods=["GET", "POST"])
@login_required
def thread(username):
    other = query_one("SELECT * FROM users WHERE username=?", (username,))
    if other is None:
        flash("Uživatel neexistuje.", "error")
        return redirect(url_for("messages_bp.inbox"))

    me = g.user["id"]

    if is_blocked(me, other["id"]):
        flash("Tento uživatel je zablokovaný, zprávy nejsou možné.", "error")
        return redirect(url_for("messages_bp.inbox"))

    other_settings = query_one("SELECT * FROM user_settings WHERE user_id=?", (other["id"],))
    privacy = other_settings["messages_privacy"] if other_settings else "friends"
    can_message = True
    if privacy == "nobody":
        can_message = False
    elif privacy == "friends" and not are_friends(me, other["id"]):
        can_message = False

    if request.method == "POST":
        if not can_message:
            return jsonify({"error": "Tento uživatel nepřijímá zprávy od cizích lidí."}), 403

        content = request.form.get("content", "").strip()
        gif_url = request.form.get("gif_url", "").strip()
        image_file = request.files.get("image")
        image_path = save_upload(image_file, "chat") if image_file and image_file.filename else None

        if not content and not gif_url and not image_path:
            return jsonify({"error": "Prázdná zpráva."}), 400

        msg_id = execute(
            "INSERT INTO messages (sender_id, recipient_id, content, image_path, gif_url) VALUES (?,?,?,?,?)",
            (me, other["id"], content, image_path, gif_url or None),
        )
        notify(other["id"], "message", actor_id=me,
               message=f"Nová zpráva od {g.user['display_name'] or g.user['username']}")

        m = query_one("SELECT * FROM messages WHERE id=?", (msg_id,))
        return jsonify({"message": _message_json(m, me)})

    execute(
        "UPDATE messages SET read_at = datetime('now') WHERE sender_id=? AND recipient_id=? AND read_at IS NULL",
        (other["id"], me),
    )

    msgs = query_all(
        """SELECT * FROM messages WHERE (sender_id=? AND recipient_id=?) OR (sender_id=? AND recipient_id=?)
           ORDER BY created_at ASC LIMIT 300""",
        (me, other["id"], other["id"], me),
    )
    return render_template("messages/thread.html", other=other, messages=msgs, can_message=can_message,
                            giphy_enabled=bool(_giphy_api_key()))


@bp.route("/<username>/poll")
@login_required
def poll(username):
    """Lehky endpoint pro AJAX dotahovani novych zprav bez reloadu stranky."""
    other = query_one("SELECT * FROM users WHERE username=?", (username,))
    if other is None:
        return jsonify({"messages": []})
    me = g.user["id"]
    if is_blocked(me, other["id"]):
        return jsonify({"messages": []})
    after_id = request.args.get("after_id", 0, type=int)
    msgs = query_all(
        """SELECT * FROM messages WHERE ((sender_id=? AND recipient_id=?) OR (sender_id=? AND recipient_id=?))
           AND id > ? ORDER BY created_at ASC""",
        (me, other["id"], other["id"], me, after_id),
    )
    if msgs:
        execute(
            "UPDATE messages SET read_at = datetime('now') WHERE sender_id=? AND recipient_id=? AND read_at IS NULL",
            (other["id"], me),
        )
    return jsonify({"messages": [_message_json(m, me) for m in msgs]})


@bp.route("/gifs/search")
@login_required
def gif_search():
    """Proxy na Giphy API, aby API klic nebyl videt v prohlizeci. Vyzaduje GIPHY_API_KEY."""
    if not _giphy_api_key():
        return jsonify({"error": "not_configured"})

    q = request.args.get("q", "").strip()
    endpoint = "search" if q else "trending"
    params = {"limit": 24, "rating": "pg-13"}
    if q:
        params["q"] = q

    data, error = _giphy_request(endpoint, params)
    if error:
        return jsonify({"error": error})

    gifs = []
    for item in data.get("data", []):
        images = item.get("images", {})
        preview = images.get("fixed_width_small") or images.get("fixed_width") or {}
        original = images.get("original") or {}
        if preview.get("url"):
            gifs.append({
                "id": item.get("id"),
                "preview_url": preview.get("url"),
                "url": original.get("url") or preview.get("url"),
            })
    return jsonify({"gifs": gifs})