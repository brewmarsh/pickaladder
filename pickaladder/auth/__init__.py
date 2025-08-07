from flask import Blueprint
from . import routes as routes

bp = Blueprint("auth", __name__, url_prefix="/auth")
