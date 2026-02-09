"""The user blueprint."""

from flask import Blueprint

from .models import FriendRequest, User
from .services import UserService

bp = Blueprint("user", __name__, url_prefix="/user", template_folder="templates")

from . import routes  # noqa: E402
from .models import FriendRequest, User  # noqa: E402
from .services import UserService  # noqa: E402

__all__ = ["FriendRequest", "User", "UserService", "routes"]
