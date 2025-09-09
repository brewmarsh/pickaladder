from flask import Blueprint

bp = Blueprint("group", __name__, url_prefix="/group")

from . import routes  # noqa: E402, F401
