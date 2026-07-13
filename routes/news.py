from flask import Blueprint, render_template

from helpers import login_required

bp = Blueprint("news_bp", __name__, url_prefix="/news")


@bp.route("")
@login_required
def view():
    return render_template("news/view.html")
