"""Blueprint for messaging routes."""

from __future__ import annotations

from flask import Blueprint

bp = Blueprint("messaging", __name__, url_prefix="/messages")

from . import routes as routes  # noqa: E402
