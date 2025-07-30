from flask import Blueprint

bp = Blueprint('match', __name__)

from . import routes
