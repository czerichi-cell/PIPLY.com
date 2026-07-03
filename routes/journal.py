import csv
import io
from datetime import datetime, timedelta

from flask import Blueprint, render_template, request, redirect, url_for, flash, g

from db import query_one, query_all, execute
from helpers import login_required, save_upload, parse_dt, week_start_for

bp = Blueprint("journal", __name__, url_prefix="/journal")

EMOTIONS = ["klidný", "sebejistý", "nervózní", "fomo", "chamtivý", "frustrovaný", "disciplinovaný", "nejistý"]


@bp.route("")
@login_required
def list_trades():
    pair = request.args.get("pair", "").strip()
    emotion = request.args.get("emotion", "").strip()

    sql = "SELECT * FROM trades WHERE user_id = ?"
    params = [g.user["id"]]
    if pair:
        sql += " AND pair LIKE ?"
        params.append(f"%{pair}%")
    if emotion:
        sql += " AND emotion = ?"
        params.append(emotion)
    sql += " ORDER BY COALESCE(closed_at, opened_at, created_at) DESC LIMIT 200"

    trades = query_all(sql, params)
    pairs = query_all(
        "SELECT DISTINCT pair FROM trades WHERE user_id = ? ORDER BY pair", (g.user["id"],)
    )
    return render_template(
        "journal/list.html", trades=trades, pairs=pairs, emotions=EMOTIONS,
        filter_pair=pair, filter_emotion=emotion,
    )


@bp.route("/new", methods=["GET", "POST"])
@login_required
def new_trade():
    if request.method == "POST":
        _save_trade_form(None)
        return redirect(url_for("journal.list_trades"))
    return render_template("journal/form.html", trade=None, emotions=EMOTIONS)


@bp.route("/<int:trade_id>/edit", methods=["GET", "POST"])
@login_required
def edit_trade(trade_id):
    trade = query_one("SELECT * FROM trades WHERE id = ? AND user_id = ?", (trade_id, g.user["id"]))
    if trade is None:
        flash("Obchod nenalezen.", "error")
        return redirect(url_for("journal.list_trades"))

    if request.method == "POST":
        _save_trade_form(trade_id)
        return redirect(url_for("journal.list_trades"))
    return render_template("journal/form.html", trade=trade, emotions=EMOTIONS)


@bp.route("/<int:trade_id>/delete", methods=["POST"])
@login_required
def delete_trade(trade_id):
    execute("DELETE FROM trades WHERE id = ? AND user_id = ?", (trade_id, g.user["id"]))
    flash("Obchod smazán.", "success")
    return redirect(url_for("journal.list_trades"))


def _save_trade_form(trade_id):
    f = request.form
    pair = f.get("pair", "").strip().upper()
    direction = f.get("direction", "buy")
    lot_size = _to_float(f.get("lot_size"))
    entry_price = _to_float(f.get("entry_price"))
    exit_price = _to_float(f.get("exit_price"))
    stop_loss = _to_float(f.get("stop_loss"))
    take_profit = _to_float(f.get("take_profit"))
    profit_loss = _to_float(f.get("profit_loss")) or 0
    rr_ratio = _to_float(f.get("rr_ratio"))
    opened_at = f.get("opened_at") or None
    closed_at = f.get("closed_at") or None
    emotion = f.get("emotion") or None
    rating = f.get("rating") or None
    notes = f.get("notes", "").strip()

    if not rr_ratio and entry_price and stop_loss and exit_price:
        risk = abs(entry_price - stop_loss)
        reward = abs(exit_price - entry_price)
        if risk > 0:
            rr_ratio = round(reward / risk, 2)

    screenshot_path = None
    file = request.files.get("screenshot")
    saved = save_upload(file, "screenshots")
    if saved:
        screenshot_path = saved

    if trade_id is None:
        execute(
            """INSERT INTO trades
               (user_id, pair, direction, lot_size, entry_price, exit_price, stop_loss, take_profit,
                profit_loss, rr_ratio, opened_at, closed_at, emotion, rating, notes, screenshot_path, source)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?, 'manual')""",
            (g.user["id"], pair, direction, lot_size, entry_price, exit_price, stop_loss, take_profit,
             profit_loss, rr_ratio, opened_at, closed_at, emotion, rating, notes, screenshot_path),
        )
        flash("Obchod přidán do deníku.", "success")
    else:
        if screenshot_path is None:
            existing = query_one("SELECT screenshot_path FROM trades WHERE id=?", (trade_id,))
            screenshot_path = existing["screenshot_path"] if existing else None
        execute(
            """UPDATE trades SET pair=?, direction=?, lot_size=?, entry_price=?, exit_price=?,
               stop_loss=?, take_profit=?, profit_loss=?, rr_ratio=?, opened_at=?, closed_at=?,
               emotion=?, rating=?, notes=?, screenshot_path=? WHERE id=? AND user_id=?""",
            (pair, direction, lot_size, entry_price, exit_price, stop_loss, take_profit,
             profit_loss, rr_ratio, opened_at, closed_at, emotion, rating, notes, screenshot_path,
             trade_id, g.user["id"]),
        )
        flash("Obchod upraven.", "success")


def _to_float(value):
    if value in (None, ""):
        return None
    try:
        return float(str(value).replace(",", ".").replace(" ", ""))
    except ValueError:
        return None


# --- MT4 / CSV import ---------------------------------------------------

COLUMN_ALIASES = {
    "pair": ["symbol", "pair", "instrument", "měna", "mena"],
    "direction": ["type", "direction", "side", "typ"],
    "lot_size": ["size", "volume", "lots", "lot", "objem"],
    "entry_price": ["open price", "price open", "openprice", "entry", "entry price", "otevírací cena"],
    "exit_price": ["close price", "price close", "closeprice", "exit", "exit price", "zavírací cena"],
    "stop_loss": ["s/l", "sl", "stop loss", "stoploss"],
    "take_profit": ["t/p", "tp", "take profit", "takeprofit"],
    "opened_at": ["open time", "opentime", "time open", "otevřeno"],
    "closed_at": ["close time", "closetime", "time close", "zavřeno"],
    "profit_loss": ["profit", "p/l", "pl", "profit_loss", "zisk", "výsledek"],
}


def _normalize_header(h):
    return h.strip().lower().replace("_", " ")


def _map_columns(fieldnames):
    normalized = {_normalize_header(h): h for h in fieldnames}
    mapping = {}
    for canonical, aliases in COLUMN_ALIASES.items():
        for alias in aliases:
            if alias in normalized:
                mapping[canonical] = normalized[alias]
                break
    return mapping


@bp.route("/import", methods=["GET", "POST"])
@login_required
def import_trades():
    if request.method == "GET":
        return render_template("journal/import.html")

    file = request.files.get("csv_file")
    if not file or file.filename == "":
        flash("Nevybral jsi žádný soubor.", "error")
        return redirect(url_for("journal.import_trades"))

    try:
        raw = file.read().decode("utf-8-sig", errors="ignore")
    except Exception:
        flash("Soubor se nepodařilo přečíst. Zkus ho uložit jako CSV (UTF-8).", "error")
        return redirect(url_for("journal.import_trades"))

    try:
        dialect = csv.Sniffer().sniff(raw[:2000], delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel

    reader = csv.DictReader(io.StringIO(raw), dialect=dialect)
    if not reader.fieldnames:
        flash("V souboru se nepodařilo najít žádné sloupce.", "error")
        return redirect(url_for("journal.import_trades"))

    mapping = _map_columns(reader.fieldnames)
    if "pair" not in mapping or "profit_loss" not in mapping:
        flash(
            "Soubor neobsahuje rozpoznatelné sloupce (potřebuju aspoň Symbol/Pair a Profit). "
            "Podívej se na vzorový CSV formát níže.",
            "error",
        )
        return redirect(url_for("journal.import_trades"))

    imported, skipped = 0, 0
    for row in reader:
        pair = (row.get(mapping.get("pair"), "") or "").strip().upper()
        profit_raw = row.get(mapping.get("profit_loss"), "")
        profit_loss = _to_float(profit_raw)
        if not pair or profit_loss is None:
            skipped += 1
            continue

        direction_raw = (row.get(mapping.get("direction", ""), "") or "").strip().lower()
        direction = "sell" if "sell" in direction_raw or direction_raw == "1" else "buy"

        entry_price = _to_float(row.get(mapping.get("entry_price", ""), ""))
        exit_price = _to_float(row.get(mapping.get("exit_price", ""), ""))
        stop_loss = _to_float(row.get(mapping.get("stop_loss", ""), ""))
        take_profit = _to_float(row.get(mapping.get("take_profit", ""), ""))
        lot_size = _to_float(row.get(mapping.get("lot_size", ""), ""))

        opened_dt = parse_dt(row.get(mapping.get("opened_at", ""), ""))
        closed_dt = parse_dt(row.get(mapping.get("closed_at", ""), ""))

        rr_ratio = None
        if entry_price and stop_loss and exit_price:
            risk = abs(entry_price - stop_loss)
            reward = abs(exit_price - entry_price)
            if risk > 0:
                rr_ratio = round(reward / risk, 2)

        execute(
            """INSERT INTO trades
               (user_id, pair, direction, lot_size, entry_price, exit_price, stop_loss, take_profit,
                profit_loss, rr_ratio, opened_at, closed_at, source)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?, 'mt4')""",
            (g.user["id"], pair, direction, lot_size, entry_price, exit_price, stop_loss, take_profit,
             profit_loss, rr_ratio,
             opened_dt.isoformat() if opened_dt else None,
             closed_dt.isoformat() if closed_dt else None),
        )
        imported += 1

    flash(f"Import hotový: {imported} obchodů naimportováno, {skipped} přeskočeno.", "success")
    return redirect(url_for("journal.list_trades"))


# --- Tydenni shrnuti ------------------------------------------------------

@bp.route("/weeks")
@login_required
def weeks():
    rows = query_all(
        """SELECT strftime('%Y-%W', COALESCE(closed_at, opened_at, created_at)) AS wk,
                  MIN(date(COALESCE(closed_at, opened_at, created_at))) AS week_start,
                  COUNT(*) AS n, COALESCE(SUM(profit_loss),0) AS pl
           FROM trades WHERE user_id = ?
           GROUP BY wk ORDER BY week_start DESC LIMIT 26""",
        (g.user["id"],),
    )
    reviews = {
        r["week_start"]: r for r in query_all(
            "SELECT * FROM weekly_reviews WHERE user_id = ?", (g.user["id"],)
        )
    }
    weeks_data = []
    for r in rows:
        ws = week_start_for(datetime.strptime(r["week_start"], "%Y-%m-%d"))
        weeks_data.append({
            "week_start": ws.isoformat(),
            "week_end": (ws + timedelta(days=6)).isoformat(),
            "count": r["n"],
            "pl": r["pl"],
            "reviewed": ws.isoformat() in reviews,
        })
    return render_template("journal/weeks.html", weeks=weeks_data)


@bp.route("/week/<week_start>", methods=["GET", "POST"])
@login_required
def week_detail(week_start):
    try:
        ws = datetime.strptime(week_start, "%Y-%m-%d").date()
    except ValueError:
        flash("Neplatné datum týdne.", "error")
        return redirect(url_for("journal.weeks"))
    we = ws + timedelta(days=6)

    if request.method == "POST":
        reflection = request.form.get("reflection", "").strip()
        rating = request.form.get("rating") or None
        existing = query_one(
            "SELECT id FROM weekly_reviews WHERE user_id=? AND week_start=?", (g.user["id"], week_start)
        )
        if existing:
            execute(
                "UPDATE weekly_reviews SET reflection=?, rating=? WHERE id=?",
                (reflection, rating, existing["id"]),
            )
        else:
            execute(
                "INSERT INTO weekly_reviews (user_id, week_start, reflection, rating) VALUES (?,?,?,?)",
                (g.user["id"], week_start, reflection, rating),
            )
        flash("Týdenní shrnutí uloženo.", "success")
        return redirect(url_for("journal.week_detail", week_start=week_start))

    trades = query_all(
        """SELECT * FROM trades WHERE user_id=?
           AND date(COALESCE(closed_at, opened_at, created_at)) BETWEEN ? AND ?
           ORDER BY COALESCE(closed_at, opened_at, created_at)""",
        (g.user["id"], ws.isoformat(), we.isoformat()),
    )
    total_pl = sum(t["profit_loss"] for t in trades)
    wins = sum(1 for t in trades if t["profit_loss"] > 0)
    winrate = round(100 * wins / len(trades), 1) if trades else 0
    review = query_one(
        "SELECT * FROM weekly_reviews WHERE user_id=? AND week_start=?", (g.user["id"], week_start)
    )

    return render_template(
        "journal/week_detail.html", trades=trades, week_start=ws, week_end=we,
        total_pl=total_pl, winrate=winrate, review=review,
    )
