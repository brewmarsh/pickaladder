"""The match blueprint."""

from flask import Blueprint

from . import routes

bp = Blueprint("match", __name__, url_prefix="/match", template_folder="templates")

__all__ = ["routes"]
