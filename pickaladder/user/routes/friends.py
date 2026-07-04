"""Social and Community routes for the user blueprint."""

from __future__ import annotations

from firebase_admin import firestore
from flask import (
    Response,
    flash,
    g,
    jsonify,
    redirect,
    render_template,
    request,
    url_for,
)

from pickaladder.auth.decorators import login_required
from pickaladder.constants.messages import COMMON_MESSAGES, USER_MESSAGES
from pickaladder.user import bp
from pickaladder.user.services import UserService
from pickaladder.user.utils import CursorPagination


@bp.route("/community")
@login_required
def view_community() -> str:
    """Render the community hub."""
    db = firestore.client()
    search_term = request.args.get("search", "").strip()

    incoming_requests = UserService.get_user_pending_requests(db, g.user.uid)
    outgoing_requests = UserService.get_user_sent_requests(db, g.user.uid)

    data = UserService.get_community_data(db, g.user.uid, search_term)

    # Filter out incoming/outgoing requests from data to avoid multiple values error
    filtered_data = {
        k: v
        for k, v in data.items()
        if k not in ["incoming_requests", "outgoing_requests"]
    }

    return render_template(
        "community.html",
        search_term=search_term,
        user=g.user,
        incoming_requests=incoming_requests,
        outgoing_requests=outgoing_requests,
        **filtered_data,
    )


@bp.route("/users")
@login_required
def users() -> str:
    """List and allows searching for users."""
    search_term = request.args.get("search", "")
    limit = request.args.get("limit", 20, type=int)
    cursor = request.args.get("cursor")

    user_items, next_cursor = UserService.search_users(
        firestore.client(),
        g.user.uid,
        search_term,
        limit=limit,
        cursor=cursor,
    )
    return render_template(
        "users.html",
        pagination=CursorPagination(user_items, next_cursor),
        search_term=search_term,
        fof=[],
    )


@bp.route("/send_friend_request/<string:friend_id>", methods=["POST"])
@login_required
def send_friend_request(friend_id: str) -> Response:
    """Send a friend request."""
    if g.user.uid == friend_id:
        flash(USER_MESSAGES["FRIEND_REQ_SELF"], "danger")
        return redirect(url_for(".users"))  # type: ignore

    success = UserService.send_friend_request(firestore.client(), g.user.uid, friend_id)
    if success:
        flash(USER_MESSAGES["FRIEND_REQ_SENT"], "success")
    else:
        flash(USER_MESSAGES["FRIEND_REQ_ERROR"], "danger")

    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return jsonify({"success": success})
    return redirect(url_for(".users"))  # type: ignore


@bp.route("/friends")
@login_required
def friends() -> Response:
    """Deprecated: Redirects to the community hub."""
    return redirect(url_for(".view_community"))  # type: ignore


@bp.route("/requests", methods=["GET"])
@login_required
def friend_requests() -> Response:
    """Deprecated: Redirects to the community hub."""
    return redirect(url_for(".view_community"))  # type: ignore


@bp.route("/requests/<string:requester_id>/accept", methods=["POST"])
@bp.route("/accept_friend_request/<string:requester_id>", methods=["POST"])
@login_required
def accept_request(requester_id: str) -> Response:
    """Accept a friend request."""
    db = firestore.client()
    requester = UserService.get_user_by_id(db, requester_id)
    name = UserService.smart_display_name(requester) if requester else "the user"

    if UserService.accept_friend_request(db, g.user.uid, requester_id):
        flash(USER_MESSAGES["FRIENDS_NOW"].format(name=name), "success")
    else:
        flash(COMMON_MESSAGES["GENERIC_ERROR_SIMPLE"], "danger")

    return redirect(request.referrer or url_for(".view_community"))  # type: ignore


@bp.route("/requests/<string:target_id>/cancel", methods=["POST"])
@bp.route("/decline_friend_request/<string:target_id>", methods=["POST"])
@login_required
def cancel_request(target_id: str) -> Response:
    """Cancel or decline a friend request."""
    if UserService.cancel_friend_request(firestore.client(), g.user.uid, target_id):
        flash(USER_MESSAGES["FRIEND_REQ_PROCESSED"], "success")
    else:
        flash(COMMON_MESSAGES["GENERIC_ERROR_SIMPLE"], "danger")
    return redirect(request.referrer or url_for(".view_community"))  # type: ignore
