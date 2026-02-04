"""Tournament blueprint."""

from flask import Blueprint

bp = Blueprint("tournament", __name__, url_prefix="/tournaments")

from . import routes  # noqa: E402, F401
