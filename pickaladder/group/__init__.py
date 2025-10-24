"""The group blueprint."""
from flask import Blueprint

from . import routes

bp = Blueprint(
    "group", __name__, url_prefix="/group", template_folder="templates"
)

__all__ = ["routes"]
