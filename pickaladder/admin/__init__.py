from flask import Blueprint
from . import routes as routes

bp = Blueprint("admin", __name__, url_prefix="/admin")
