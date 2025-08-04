from flask import Blueprint

bp = Blueprint("match", __name__, url_prefix="/match")

from . import routes
