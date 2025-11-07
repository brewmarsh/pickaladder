"""The group blueprint."""

from flask import Blueprint

bp = Blueprint("group", __name__, url_prefix="/group", template_folder="templates")

from . import routes  # noqa: E402

__all__ = ["routes"]
