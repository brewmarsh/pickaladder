"""The match blueprint."""

from flask import Blueprint

bp = Blueprint("match", __name__, url_prefix="/match", template_folder="templates")

from . import routes  # noqa: E402
from .models import Match, Score
from .services import MatchService

__all__ = ["Match", "MatchService", "Score", "routes"]
