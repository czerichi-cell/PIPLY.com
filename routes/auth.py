import secrets
from datetime import datetime, timedelta

from flask import Blueprint, render_template, request, redirect, url_for, session, flash, g
from werkzeug.security import generate_password_hash, check_password_hash

from db import query_one, execute
from mail import send_email

bp = Blueprint("auth", __name__, url_prefix="/auth")

RESERVED_USERNAMES = {"settings", "search", "admin", "api", "static", "auth", "u", "gifs"}


@bp.route("/register", methods=["GET", "POST"])
def register():
    if g.user:
        return redirect(url_for("social.feed"))

    if request.method == "POST":
        username = request.form.get("username", "").strip().lower()
        email = request.form.get("email", "").strip().lower()
        display_name = request.form.get("display_name", "").strip() or username
        password = request.form.get("password", "")
        password2 = request.form.get("password2", "")

        error = None
        if not username or len(username) < 3:
            error = "Uživatelské jméno musí mít aspoň 3 znaky."
        elif not username.replace("_", "").isalnum():
            error = "Uživatelské jméno smí obsahovat jen písmena, čísla a podtržítko."
        elif not email or "@" not in email or "." not in email.split("@")[-1]:
            error = "Zadej prosím platnou e-mailovou adresu."
        elif not password or len(password) < 6:
            error = "Heslo musí mít aspoň 6 znaků."
        elif password != password2:
            error = "Hesla se neshodují."
        elif username in RESERVED_USERNAMES:
            error = "Toto uživatelské jméno je rezervované, zvol prosím jiné."
        elif query_one("SELECT id FROM users WHERE username = ?", (username,)):
            error = "Toto uživatelské jméno už je zabrané."
        elif query_one("SELECT id FROM users WHERE email = ?", (email,)):
            error = "Tento e-mail už je zaregistrovaný."

        if error:
            flash(error, "error")
            return render_template("auth/register.html", form=request.form)

        user_id = execute(
            "INSERT INTO users (username, email, password_hash, display_name) VALUES (?,?,?,?)",
            (username, email, generate_password_hash(password), display_name),
        )
        execute("INSERT INTO user_settings (user_id) VALUES (?)", (user_id,))
        session.clear()
        session["user_id"] = user_id
        session.permanent = True
        flash("Vítej v Piply! Účet byl vytvořen.", "success")
        return redirect(url_for("profile.edit_profile", first_time=1))

    return render_template("auth/register.html", form={})


@bp.route("/login", methods=["GET", "POST"])
def login():
    if g.user:
        return redirect(url_for("social.feed"))

    if request.method == "POST":
        identifier = request.form.get("username", "").strip().lower()
        password = request.form.get("password", "")
        user = query_one(
            "SELECT * FROM users WHERE username = ? OR email = ?", (identifier, identifier)
        )
        if user is None or not check_password_hash(user["password_hash"], password):
            flash("Neplatné přihlašovací jméno nebo heslo.", "error")
            return render_template("auth/login.html")

        if user["is_banned"]:
            flash("Tento účet byl zablokován. Pokud si myslíš, že jde o omyl, kontaktuj podporu.", "error")
            return render_template("auth/login.html")

        session.clear()
        session["user_id"] = user["id"]
        session.permanent = bool(request.form.get("remember"))
        nxt = request.args.get("next")
        return redirect(nxt or url_for("social.feed"))

    return render_template("auth/login.html")


@bp.route("/logout")
def logout():
    session.clear()
    flash("Byl jsi odhlášen.", "success")
    return redirect(url_for("auth.login"))


@bp.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        user = query_one("SELECT * FROM users WHERE email = ?", (email,)) if email else None

        if user:
            token = secrets.token_urlsafe(32)
            expires_at = (datetime.utcnow() + timedelta(hours=1)).isoformat()
            execute(
                "INSERT INTO password_reset_tokens (user_id, token, expires_at) VALUES (?,?,?)",
                (user["id"], token, expires_at),
            )
            reset_url = url_for("auth.reset_password", token=token, _external=True)
            send_email(
                user["email"],
                "Obnovení hesla – Piply",
                f"Ahoj {user['display_name'] or user['username']},\n\n"
                f"někdo (doufejme ty) požádal o obnovení hesla k účtu na Piply.\n\n"
                f"Klikni na odkaz níže a nastav si nové heslo. Odkaz je platný 1 hodinu:\n"
                f"{reset_url}\n\n"
                f"Pokud jsi o obnovení hesla nežádal(a), tenhle e-mail prostě ignoruj – "
                f"tvoje heslo zůstane beze změny.\n\nPiply",
            )

        # Zamerne stejna hláška bez ohledu na to, jestli e-mail v databazi existuje -
        # jinak by šlo timhle formularem zjistit, ktere e-maily jsou u nas registrovane.
        flash("Pokud je tenhle e-mail u nás registrovaný, poslali jsme na něj odkaz na obnovení hesla.", "success")
        return redirect(url_for("auth.login"))

    return render_template("auth/forgot_password.html")


@bp.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password(token):
    row = query_one("SELECT * FROM password_reset_tokens WHERE token = ?", (token,))
    valid = (
        row is not None
        and not row["used"]
        and datetime.fromisoformat(row["expires_at"]) > datetime.utcnow()
    )

    if not valid:
        flash("Odkaz na obnovení hesla je neplatný nebo už vypršel. Zkus si o něj požádat znovu.", "error")
        return redirect(url_for("auth.forgot_password"))

    if request.method == "POST":
        password = request.form.get("password", "")
        password2 = request.form.get("password2", "")

        if not password or len(password) < 6:
            flash("Heslo musí mít aspoň 6 znaků.", "error")
            return render_template("auth/reset_password.html", token=token)
        if password != password2:
            flash("Hesla se neshodují.", "error")
            return render_template("auth/reset_password.html", token=token)

        execute("UPDATE users SET password_hash=? WHERE id=?", (generate_password_hash(password), row["user_id"]))
        execute("UPDATE password_reset_tokens SET used=1 WHERE id=?", (row["id"],))
        flash("Heslo bylo úspěšně změněno. Teď se můžeš přihlásit.", "success")
        return redirect(url_for("auth.login"))

    return render_template("auth/reset_password.html", token=token)