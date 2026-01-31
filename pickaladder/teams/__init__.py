"""Blueprint for the teams feature."""

from flask import Blueprint

bp = Blueprint(
    "teams",
    __name__,
    url_prefix="/team",
)

from . import routes  # noqa: E402, F401
