from flask import Blueprint
from . import routes as routes

bp = Blueprint("user", __name__, url_prefix="/user")
