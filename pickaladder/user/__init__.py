"""The user blueprint."""

from flask import Blueprint

bp = Blueprint("user", __name__, url_prefix="/user", template_folder="templates")

from . import routes

__all__ = ["routes"]
