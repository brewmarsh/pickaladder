"""The admin blueprint."""

from flask import Blueprint

from . import routes

bp = Blueprint("admin", __name__, url_prefix="/admin", template_folder="templates")

__all__ = ["routes"]
