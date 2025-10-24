"""The admin blueprint."""

from flask import Blueprint

bp = Blueprint("admin", __name__, url_prefix="/admin", template_folder="templates")

from . import routes

__all__ = ["routes"]
