"""The user blueprint."""

from flask import Blueprint

bp = Blueprint("user", __name__, url_prefix="/user", template_folder="templates")

from . import routes  # noqa: E402

__all__ = ["routes"]
