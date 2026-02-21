"""The auth blueprint."""

from flask import Blueprint

from .services import AuthService

bp = Blueprint("auth", __name__, url_prefix="/auth", template_folder="templates")

from . import routes  # noqa: E402

__all__ = ["AuthService", "routes"]
