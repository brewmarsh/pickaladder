"""The user blueprint."""
from flask import Blueprint

from . import routes

bp = Blueprint("user", __name__, url_prefix="/user", template_folder="templates")

__all__ = ["routes"]
