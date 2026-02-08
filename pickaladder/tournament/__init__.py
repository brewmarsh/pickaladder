"""Tournament blueprint."""

from flask import Blueprint

bp = Blueprint("tournament", __name__, url_prefix="/tournaments")

from . import routes  # noqa: E402, F401
from .models import Participant, Tournament
from .services import TournamentService

__all__ = ["Participant", "Tournament", "TournamentService", "routes"]
