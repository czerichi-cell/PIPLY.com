from flask import Blueprint, render_template, request, redirect, url_for, session, flash, g
from werkzeug.security import generate_password_hash, check_password_hash

from db import query_one, execute

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
        elif not password or len(password) < 6:
            error = "Heslo musí mít aspoň 6 znaků."
        elif password != password2:
            error = "Hesla se neshodují."
        elif username in RESERVED_USERNAMES:
            error = "Toto uživatelské jméno je rezervované, zvol prosím jiné."
        elif query_one("SELECT id FROM users WHERE username = ?", (username,)):
            error = "Toto uživatelské jméno už je zabrané."
        elif email and query_one("SELECT id FROM users WHERE email = ?", (email,)):
            error = "Tento e-mail už je zaregistrovaný."

        if error:
            flash(error, "error")
            return render_template("auth/register.html", form=request.form)

        user_id = execute(
            "INSERT INTO users (username, email, password_hash, display_name) VALUES (?,?,?,?)",
            (username, email or None, generate_password_hash(password), display_name),
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