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
