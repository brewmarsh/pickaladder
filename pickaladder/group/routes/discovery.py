"""Discovery routes for the group blueprint."""

from __future__ import annotations

from firebase_admin import firestore
from flask import g, render_template, request, session

from pickaladder.auth.decorators import login_required
from pickaladder.group import bp
from pickaladder.group.services.group_service import GroupService


@bp.route("/", methods=["GET"])
@login_required
def view_groups() -> Response | str | dict[str, object]:
    """Display the user's groups."""
    db = firestore.client()
    enriched_my_groups = GroupService.get_user_groups(db, g.user.uid)

    return render_template(
        "groups.html",
        my_groups=enriched_my_groups,
    )


def _handle_referrer() -> None:
    """Capture referrer ID from request arguments into session."""
    if "ref" in request.args:
        session["referrer_id"] = request.args.get("ref")
