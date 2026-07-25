import calendar as calendar_module
import re
from datetime import date, datetime, timedelta

from flask import Blueprint, render_template, request, redirect, url_for, flash, g

from db import query_one, query_all, execute
from helpers import login_required, are_friends, notify

bp = Blueprint("calendar_bp", __name__, url_prefix="/calendar")

CZ_MONTHS = [
    "Leden", "Únor", "Březen", "Duben", "Květen", "Červen",
    "Červenec", "Srpen", "Září", "Říjen", "Listopad", "Prosinec",
]
CZ_DAYS = ["Po", "Út", "St", "Čt", "Pá", "So", "Ne"]


def _parse_month(month_str):
    try:
        y, m = month_str.split("-")
        return int(y), int(m)
    except (ValueError, AttributeError):
        today = date.today()
        return today.year, today.month


def _shift_month(year, month, delta):
    total = (year * 12 + (month - 1)) + delta
    return total // 12, (total % 12) + 1


@bp.route("")
@login_required
def view():
    me = g.user["id"]
    month_str = request.args.get("month", "")
    year, month = _parse_month(month_str)
    selected_date = request.args.get("date", "")

    first_weekday, days_in_month = calendar_module.monthrange(year, month)
    month_key = f"{year:04d}-{month:02d}"
    prev_year, prev_month = _shift_month(year, month, -1)
    next_year, next_month = _shift_month(year, month, 1)

    range_start = f"{year:04d}-{month:02d}-01"
    range_end = f"{year:04d}-{month:02d}-{days_in_month:02d}"

    events = query_all(
        """SELECT calendar_events.*, users.username AS owner_username,
                  users.display_name AS owner_display_name
           FROM calendar_events
           JOIN users ON users.id = calendar_events.user_id
           WHERE calendar_events.event_date BETWEEN ? AND ?
             AND (
               calendar_events.user_id = ?
               OR calendar_events.id IN (
                   SELECT event_id FROM calendar_invites
                   WHERE invitee_id = ? AND status = 'accepted'
               )
             )
           ORDER BY calendar_events.event_time IS NULL, calendar_events.event_time, calendar_events.id""",
        (range_start, range_end, me, me),
    )

    events_by_day = {}
    for e in events:
        events_by_day.setdefault(e["event_date"], []).append(e)

    weeks = []
    week = [None] * first_weekday
    for day in range(1, days_in_month + 1):
        week.append(day)
        if len(week) == 7:
            weeks.append(week)
            week = []
    if week:
        while len(week) < 7:
            week.append(None)
        weeks.append(week)

    friends = query_all(
        """SELECT u.id, u.username, u.display_name FROM users u
           JOIN friendships f ON (
               (f.requester_id = u.id AND f.addressee_id = ?) OR
               (f.addressee_id = u.id AND f.requester_id = ?)
           )
           WHERE f.status = 'accepted' ORDER BY u.display_name""",
        (me, me),
    )

    today_str = date.today().isoformat()

    events_json = {}
    for day_str, day_events in events_by_day.items():
        events_json[day_str] = [
            {
                "id": e["id"], "title": e["title"], "time": e["event_time"],
                "kind": e["kind"], "is_done": bool(e["is_done"]),
                "color": e["color"] or "#7ed957", "icon": e["icon"] or "📌",
                "priority": e["priority"] or "medium",
                "is_mine": e["user_id"] == me,
                "owner_name": e["owner_display_name"] or e["owner_username"],
            }
            for e in day_events
        ]

    return render_template(
        "calendar/view.html",
        year=year, month=month, month_key=month_key,
        month_name=CZ_MONTHS[month - 1], day_names=CZ_DAYS,
        weeks=weeks, events_by_day=events_by_day, events_json=events_json,
        prev_month_key=f"{prev_year:04d}-{prev_month:02d}",
        next_month_key=f"{next_year:04d}-{next_month:02d}",
        friends=friends, selected_date=selected_date or today_str,
        today_str=today_str,
    )


@bp.route("/new", methods=["POST"])
@login_required
def new_event():
    me = g.user["id"]
    title = request.form.get("title", "").strip()
    notes = request.form.get("notes", "").strip()
    event_date = request.form.get("event_date", "").strip()
    event_time = request.form.get("event_time", "").strip() or None
    kind = request.form.get("kind", "task")
    if kind not in ("task", "note"):
        kind = "task"
    color = request.form.get("color", "#7ed957").strip()
    if not re.match(r"^#[0-9a-fA-F]{6}$", color):
        color = "#7ed957"
    icon = request.form.get("icon", "📌").strip()[:8] or "📌"
    priority = request.form.get("priority", "medium")
    if priority not in ("low", "medium", "high"):
        priority = "medium"
    invite_username = request.form.get("invite_username", "").strip()
    month_key = request.form.get("month_key", "")

    if not title or not event_date:
        flash("Vyplň prosím název a datum.", "error")
        return redirect(url_for("calendar_bp.view", month=month_key, date=event_date))

    event_id = execute(
        """INSERT INTO calendar_events (user_id, title, notes, event_date, event_time, kind, color, icon, priority)
           VALUES (?,?,?,?,?,?,?,?,?)""",
        (me, title, notes, event_date, event_time, kind, color, icon, priority),
    )

    if invite_username:
        friend = query_one("SELECT * FROM users WHERE username=?", (invite_username,))
        if friend and friend["id"] != me and are_friends(me, friend["id"]):
            invite_id = execute(
                """INSERT INTO calendar_invites (event_id, inviter_id, invitee_id, status)
                   VALUES (?,?,?, 'pending')""",
                (event_id, me, friend["id"]),
            )
            when = f"{event_date}" + (f" {event_time}" if event_time else "")
            content = f"📅 Pozvánka do kalendáře: „{title}“ ({when})"
            execute(
                """INSERT INTO messages (sender_id, recipient_id, content, invite_id)
                   VALUES (?,?,?,?)""",
                (me, friend["id"], content, invite_id),
            )
            notify(
                friend["id"], "calendar_invite", actor_id=me, target_id=invite_id,
                message=f"Pozval{'a' if g.user['display_name'] else ''} tě do kalendářové události „{title}“",
            )
            flash(f"Událost vytvořena a pozvánka odeslána uživateli {friend['display_name'] or friend['username']}.", "success")
        else:
            flash("Událost vytvořena, ale pozvánku se nepodařilo odeslat (uživatel není tvůj přítel).", "error")
    else:
        flash("Událost vytvořena.", "success")

    return redirect(url_for("calendar_bp.view", month=month_key or event_date[:7], date=event_date))


@bp.route("/<int:event_id>/detail")
@login_required
def event_detail(event_id):
    me = g.user["id"]
    ev = query_one(
        """SELECT calendar_events.*, users.username AS owner_username, users.display_name AS owner_display_name
           FROM calendar_events JOIN users ON users.id = calendar_events.user_id
           WHERE calendar_events.id=?""",
        (event_id,),
    )
    if not ev:
        return {"error": "not_found"}, 404

    is_owner = ev["user_id"] == me
    has_access = is_owner or query_one(
        "SELECT 1 FROM calendar_invites WHERE event_id=? AND invitee_id=? AND status='accepted'",
        (event_id, me),
    )
    if not has_access:
        return {"error": "forbidden"}, 403

    invites = query_all(
        """SELECT calendar_invites.status, users.username, users.display_name
           FROM calendar_invites JOIN users ON users.id = calendar_invites.invitee_id
           WHERE calendar_invites.event_id=?
           ORDER BY calendar_invites.created_at""",
        (event_id,),
    )

    return {
        "id": ev["id"],
        "title": ev["title"],
        "notes": ev["notes"],
        "date": ev["event_date"],
        "time": ev["event_time"],
        "kind": ev["kind"],
        "is_done": bool(ev["is_done"]),
        "color": ev["color"] or "#7ed957",
        "icon": ev["icon"] or "📌",
        "priority": ev["priority"] or "medium",
        "is_owner": is_owner,
        "owner_name": ev["owner_display_name"] or ev["owner_username"],
        "invites": [
            {"name": i["display_name"] or i["username"], "status": i["status"]}
            for i in invites
        ],
    }


@bp.route("/<int:event_id>/toggle", methods=["POST"])
@login_required
def toggle_event(event_id):
    ev = query_one("SELECT * FROM calendar_events WHERE id=?", (event_id,))
    month_key = request.form.get("month_key", "")
    if ev and ev["user_id"] == g.user["id"]:
        execute("UPDATE calendar_events SET is_done = 1 - is_done WHERE id=?", (event_id,))
    return redirect(url_for("calendar_bp.view", month=month_key or (ev["event_date"][:7] if ev else "")))


@bp.route("/<int:event_id>/delete", methods=["POST"])
@login_required
def delete_event(event_id):
    ev = query_one("SELECT * FROM calendar_events WHERE id=?", (event_id,))
    month_key = request.form.get("month_key", "")
    if ev and ev["user_id"] == g.user["id"]:
        execute("DELETE FROM calendar_events WHERE id=?", (event_id,))
        flash("Událost smazána.", "success")
    return redirect(url_for("calendar_bp.view", month=month_key or (ev["event_date"][:7] if ev else "")))


@bp.route("/invite/<int:invite_id>/respond", methods=["POST"])
@login_required
def respond_invite(invite_id):
    """Prijmout/odmitnout pozvanku - vola se z chatu (karticka u zpravy)."""
    action = request.form.get("action", "")
    invite = query_one("SELECT * FROM calendar_invites WHERE id=?", (invite_id,))
    if not invite or invite["invitee_id"] != g.user["id"]:
        return {"error": "not_found"}, 404
    if invite["status"] != "pending":
        return {"status": invite["status"]}

    new_status = "accepted" if action == "accept" else "declined"
    execute(
        "UPDATE calendar_invites SET status=?, responded_at=datetime('now') WHERE id=?",
        (new_status, invite_id),
    )

    event = query_one("SELECT * FROM calendar_events WHERE id=?", (invite["event_id"],))
    if event:
        verb = "přijal/a" if new_status == "accepted" else "odmítl/a"
        notify(
            invite["inviter_id"], "calendar_invite_response", actor_id=g.user["id"],
            target_id=invite_id,
            message=f"{verb} pozvánku do události „{event['title']}“",
        )

    return {"status": new_status}
