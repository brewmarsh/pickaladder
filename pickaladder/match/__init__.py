"""The match blueprint."""

from flask import Blueprint

from .models import Match, Score
from .services import MatchCommandService, MatchQueryService

bp = Blueprint("match", __name__, url_prefix="/match", template_folder="templates")

from . import routes  # noqa: E402

__all__ = ["Match", "MatchQueryService", "MatchCommandService", "Score", "routes"]
