import os
from pathlib import Path
from datetime import timedelta

from flask import Flask, g, render_template, redirect, url_for

from db import register_db, init_db
from helpers import (
    load_logged_in_user,
    unread_notification_count,
    unread_message_count,
    fmt_dt,
)

BASE_DIR = Path(__file__).resolve().parent


def create_app():
    app = Flask(__name__)
    app.config["SECRET_KEY"] = os.environ.get("TRADER_HUB_SECRET", "dev-secret-zmen-si-me-pred-nasazenim")
    app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 16 MB limit na upload
    app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(days=365)

    register_db(app)

    with app.app_context():
        init_db()

    app.before_request(load_logged_in_user)

    # Jinja filtry / globalni promenne dostupne ve vsech sablonach
    app.jinja_env.filters["dt"] = fmt_dt

    @app.context_processor
    def inject_globals():
        if g.get("user"):
            return {
                "current_user": g.user,
                "notif_count": unread_notification_count(g.user["id"]),
                "msg_count": unread_message_count(g.user["id"]),
            }
        return {"current_user": None, "notif_count": 0, "msg_count": 0}

    # --- Registrace blueprintu ---
    from routes.auth import bp as auth_bp
    from routes.profile import bp as profile_bp
    from routes.journal import bp as journal_bp
    from routes.stats import bp as stats_bp
    from routes.social import bp as social_bp
    from routes.messages_bp import bp as messages_bp
    from routes.notifications import bp as notifications_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(profile_bp)
    app.register_blueprint(journal_bp)
    app.register_blueprint(stats_bp)
    app.register_blueprint(social_bp)
    app.register_blueprint(messages_bp)
    app.register_blueprint(notifications_bp)

    @app.route("/")
    def index():
        if g.user:
            return redirect(url_for("social.feed"))
        return redirect(url_for("auth.login"))

    @app.route("/api/live-counts")
    def live_counts():
        from flask import jsonify
        if not g.user:
            return jsonify({"unread_messages": 0, "unread_notifications": 0})
        return jsonify({
            "unread_messages": unread_message_count(g.user["id"]),
            "unread_notifications": unread_notification_count(g.user["id"]),
        })

    @app.errorhandler(404)
    def not_found(e):
        return render_template("error.html", code=404, message="Stránka nenalezena."), 404

    @app.errorhandler(413)
    def too_large(e):
        return render_template("error.html", code=413, message="Soubor je příliš velký (max 16 MB)."), 413

    return app


app = create_app()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    host = os.environ.get("HOST", "127.0.0.1")
    debug = os.environ.get("DEBUG", "1") == "1"
    print(f"\n  Piply bezi na http://{host}:{port}  (Ctrl+C pro ukonceni)\n")
    app.run(host=host, port=port, debug=debug, threaded=True)