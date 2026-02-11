from flask import Blueprint

bp = Blueprint("main", __name__)

from . import routes as routes  # noqa: E402, F401
