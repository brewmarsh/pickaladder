from flask import Blueprint
from . import routes as routes

bp = Blueprint("match", __name__, url_prefix="/match")
