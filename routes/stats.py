import json
from flask import Blueprint, render_template, g

from db import query_all

bp = Blueprint("stats", __name__, url_prefix="/stats")


@bp.route("")
@bp.route("/")
def dashboard():
    from flask import redirect, url_for
    if not g.user:
        return redirect(url_for("auth.login"))

    trades = query_all(
        """SELECT * FROM trades WHERE user_id = ?
           ORDER BY COALESCE(closed_at, opened_at, created_at) ASC""",
        (g.user["id"],),
    )

    n = len(trades)
    if n == 0:
        return render_template("stats/dashboard.html", has_data=False)

    total_pl = sum(t["profit_loss"] for t in trades)
    wins = [t for t in trades if t["profit_loss"] > 0]
    losses = [t for t in trades if t["profit_loss"] < 0]
    winrate = round(100 * len(wins) / n, 1)
    avg_win = round(sum(t["profit_loss"] for t in wins) / len(wins), 2) if wins else 0
    avg_loss = round(sum(t["profit_loss"] for t in losses) / len(losses), 2) if losses else 0
    rr_values = [t["rr_ratio"] for t in trades if t["rr_ratio"]]
    avg_rr = round(sum(rr_values) / len(rr_values), 2) if rr_values else None
    profit_factor = None
    gross_win = sum(t["profit_loss"] for t in wins)
    gross_loss = abs(sum(t["profit_loss"] for t in losses))
    if gross_loss > 0:
        profit_factor = round(gross_win / gross_loss, 2)

    # equity krivka + max drawdown
    starting = g.user["starting_capital"] or 0
    equity = starting
    equity_curve = [{"label": "start", "equity": equity}]
    peak = equity
    max_dd = 0
    max_dd_pct = 0
    for t in trades:
        equity += t["profit_loss"]
        label_date = t["closed_at"] or t["opened_at"] or t["created_at"] or ""
        equity_curve.append({"label": str(label_date)[:16], "equity": round(equity, 2)})
        if equity > peak:
            peak = equity
        dd = peak - equity
        if dd > max_dd:
            max_dd = dd
            max_dd_pct = round(100 * dd / peak, 1) if peak > 0 else 0

    # rozpad podle meny
    by_pair = {}
    for t in trades:
        by_pair.setdefault(t["pair"], {"pair": t["pair"], "count": 0, "pl": 0, "wins": 0})
        by_pair[t["pair"]]["count"] += 1
        by_pair[t["pair"]]["pl"] += t["profit_loss"]
        if t["profit_loss"] > 0:
            by_pair[t["pair"]]["wins"] += 1
    pair_stats = sorted(by_pair.values(), key=lambda x: -abs(x["pl"]))
    for p in pair_stats:
        p["pl"] = round(p["pl"], 2)
        p["winrate"] = round(100 * p["wins"] / p["count"], 1)

    # rozpad podle emoce
    by_emotion = {}
    for t in trades:
        if not t["emotion"]:
            continue
        by_emotion.setdefault(t["emotion"], {"emotion": t["emotion"], "count": 0, "pl": 0})
        by_emotion[t["emotion"]]["count"] += 1
        by_emotion[t["emotion"]]["pl"] += t["profit_loss"]
    emotion_stats = sorted(by_emotion.values(), key=lambda x: -x["count"])
    for e in emotion_stats:
        e["pl"] = round(e["pl"], 2)

    chart_data = {
        "equity_labels": [e["label"] for e in equity_curve],
        "equity_values": [e["equity"] for e in equity_curve],
        "starting_capital": starting,
        "pair_labels": [p["pair"] for p in pair_stats[:10]],
        "pair_values": [p["pl"] for p in pair_stats[:10]],
        "win_loss": [len(wins), len(losses), n - len(wins) - len(losses)],
    }

    return render_template(
        "stats/dashboard.html",
        has_data=True,
        n=n, total_pl=round(total_pl, 2), winrate=winrate,
        avg_win=avg_win, avg_loss=avg_loss, avg_rr=avg_rr, profit_factor=profit_factor,
        max_dd=round(max_dd, 2), max_dd_pct=max_dd_pct,
        pair_stats=pair_stats, emotion_stats=emotion_stats,
        chart_data=json.dumps(chart_data),
    )
