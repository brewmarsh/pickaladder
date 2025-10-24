"""The auth blueprint."""

from flask import Blueprint

from . import routes

bp = Blueprint("auth", __name__, url_prefix="/auth", template_folder="templates")

__all__ = ["routes"]
