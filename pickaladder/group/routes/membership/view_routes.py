from typing import Any

from firebase_admin import firestore
from flask import flash, g, redirect, render_template, request, url_for
from werkzeug.wrappers import Response

from pickaladder.auth.decorators import login_required
from pickaladder.constants.messages import GROUP_MESSAGES
from pickaladder.group import bp
from pickaladder.group.routes.discovery import _handle_referrer
from pickaladder.group.routes.membership.invite_forms import (
    _handle_invite_email_form,
    _handle_invite_friend_form,
)
from pickaladder.group.services.group_service import (
    AccessDenied,
    GroupNotFound,
    GroupService,
)


@bp.route("/<string:group_id>", methods=["GET", "POST"])
@login_required
def view_group(group_id: str) -> Response | str | dict[str, Any]:
    """Display a single group's page."""
    _handle_referrer()

    db = firestore.client()
    player_a_id = request.args.get("playerA")
    player_b_id = request.args.get("playerB")

    try:
        context = GroupService.get_group_details(
            db,
            group_id,
            g.user.uid,
            player_a_id,
            player_b_id,
        )
    except GroupNotFound:
        flash(GROUP_MESSAGES["NOT_FOUND"], "danger")
        return redirect(url_for(".view_groups"))  # type: ignore
    except AccessDenied:
        flash(GROUP_MESSAGES["ACCESS_DENIED"], "danger")
        return redirect(url_for(".view_groups"))  # type: ignore

    form, resp = _handle_invite_friend_form(db, group_id, context)
    if resp:
        return resp

    invite_email_form, resp = _handle_invite_email_form(
        db,
        group_id,
        context["group"].get("name", "Unknown Group"),
        g.user.uid,
    )
    if resp:
        return resp

    # 10. Fetch Seasons
    from pickaladder.season.services import SeasonService

    context["seasons"] = SeasonService.get_seasons_for_group(db, group_id)

    return render_template(
        "group.html",
        form=form,
        invite_email_form=invite_email_form,
        **context,
    )
