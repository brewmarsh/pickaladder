"""Season blueprint initialization."""

from flask import Blueprint

bp = Blueprint("season", __name__, url_prefix="/season")

from . import routes  # noqa: E402, F401
