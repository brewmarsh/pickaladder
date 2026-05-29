<<<<<<< HEAD
from flask import Blueprint

bp = Blueprint("marketplace", __name__, url_prefix="/marketplace")

from . import routes  # noqa: F401
=======
"""The marketplace blueprint."""

from flask import Blueprint

bp = Blueprint(
    "marketplace",
    __name__,
    url_prefix="/marketplace",
    template_folder="../templates/marketplace",
)

from . import routes  # noqa: E402

__all__ = ["routes"]
>>>>>>> 395736a075685dfc196237a25821dffdb0346839
