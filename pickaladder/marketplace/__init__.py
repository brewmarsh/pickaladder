from flask import Blueprint

bp = Blueprint("marketplace", __name__, url_prefix="/marketplace")

from . import routes  # noqa: F401
