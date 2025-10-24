"""The match blueprint."""

from flask import Blueprint

bp = Blueprint("match", __name__, url_prefix="/match", template_folder="templates")

from . import routes  # noqa: E402

__all__ = ["routes"]
