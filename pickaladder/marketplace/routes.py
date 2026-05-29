from flask import render_template
from . import bp

@bp.route("/", methods=["GET"])
def index():
    return render_template("marketplace/index.html")
