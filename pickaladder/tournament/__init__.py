"""Tournament blueprint."""

from flask import Blueprint

from .models import Participant, Tournament
from .services import TournamentService

bp = Blueprint("tournament", __name__, url_prefix="/tournaments")

from . import routes  # noqa: E402, F401

__all__ = ["Participant", "Tournament", "TournamentService", "routes"]
