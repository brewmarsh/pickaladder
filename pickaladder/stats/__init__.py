"""Stats blueprint for match predictions and other statistical utilities."""

from flask import Blueprint

bp = Blueprint("stats", __name__, url_prefix="/stats")

from . import routes  # noqa: E402, F401
