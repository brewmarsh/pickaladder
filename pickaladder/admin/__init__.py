"""The admin blueprint."""

from flask import Blueprint

bp = Blueprint("admin", __name__, url_prefix="/admin", template_folder="templates")

from . import routes  # noqa: E402

__all__ = ["routes"]
from . import dev_routes  # noqa: F401
from . import feedback_routes  # noqa: F401
from . import user_mgmt_routes  # noqa: F401
from . import match_routes  # noqa: F401
