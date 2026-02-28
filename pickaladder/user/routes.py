"""Routes for the user blueprint."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from firebase_admin import firestore
from flask import (
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
from pickaladder.core.constants import DUPR_PROFILE_BASE_URL

from . import bp
from .forms import SettingsForm, UpdateUserForm
from .services import UserService

if TYPE_CHECKING:
    pass


class MockPagination:
    """A mock pagination object."""

    def __init__(self, items: list[Any]) -> None:
        """Initialize the mock pagination object."""
        self.items = items
        self.pages = 1


@bp.route("/settings", methods=["GET", "POST"])
@login_required
def settings() -> Any:
    """Unified user settings page."""
    db = firestore.client()
    user_id = g.user["uid"]
    form = SettingsForm()

    if request.method == "GET":
        form.name.data = g.user.get("name")
        form.username.data = g.user.get("username")
        form.email.data = g.user.get("email")
        form.dupr_id.data = g.user.get("dupr_id")
        form.dupr_rating.data = g.user.get("duprRating") or g.user.get("dupr_rating")
        form.dark_mode.data = g.user.get("dark_mode")

    if form.validate_on_submit():
        # Use the consolidated service call
        res = UserService.process_profile_update(
            db, user_id, form, g.user, form.profile_picture.data
        )

        if res["success"]:
            if "info" in res:
                flash(res["info"], "info")
            flash(USER_MESSAGES["SETTINGS_UPDATED"], "success")
            return redirect(url_for(".settings"))
        flash(res["error"], "danger")

    return render_template("user/settings.html", form=form, user=g.user)


@bp.route("/settings/reset_avatar", methods=["POST"])
@login_required
def reset_avatar() -> Any:
    """Reset the user's avatar to default."""
    db = firestore.client()
    user_id = g.user["uid"]
    if UserService.reset_profile_picture(db, user_id):
        flash(USER_MESSAGES["PROFILE_PIC_REMOVED"], "success")
    else:
        flash(USER_MESSAGES["PROFILE_PIC_REMOVE_ERROR"], "danger")
    return redirect(url_for(".settings"))


@bp.route("/edit_profile", methods=["GET", "POST"])
@login_required
def edit_profile() -> Any:
    """Handle user profile updates."""
    form = UpdateUserForm(data=g.user)
    if form.validate_on_submit():
        res = UserService.process_profile_update(
            firestore.client(), g.user["uid"], form, g.user
        )
        if res["success"]:
            if "info" in res:
                flash(res["info"], "info")
            flash(USER_MESSAGES["ACCOUNT_UPDATED"], "success")
            return redirect(url_for(".edit_profile"))
        flash(res["error"], "danger")
    return render_template("user/edit_profile.html", form=form, user=g.user)


@bp.route("/dashboard", methods=["GET", "POST"])
@login_required
def dashboard() -> Any:
    """Render user dashboard."""
    db = firestore.client()
    user_id = g.user["uid"]

    data = UserService.get_dashboard_data(db, user_id)

    # Remove user from data to avoid conflict with g.user passed to template
    data.pop("user", None)

    return render_template(
        "user_dashboard.html",
        user=g.user,
        **data,
    )


@bp.route("/<string:user_id>")
@login_required
def view_user(user_id: str) -> Any:
    """Display a user's public profile."""
    db = firestore.client()
    data = UserService.get_user_profile_data(db, g.user["uid"], user_id)
    if not data:
        flash(USER_MESSAGES["NOT_FOUND"], "danger")
        return redirect(url_for(".users"))

    stats = data.get("stats", {})
    total_games = stats.get("total_games", 0)

    return render_template(
        "user/profile.html",
        user=g.user,
        dupr_url_base=DUPR_PROFILE_BASE_URL,
        record={"wins": stats.get("wins", 0), "losses": stats.get("losses", 0)},
        total_games=total_games,
        win_rate=stats.get("win_rate", 0),
        current_streak=stats.get("current_streak", 0),
        streak_type=stats.get("streak_type", "N/A"),
        **data,
    )


@bp.route("/community")
@login_required
def view_community() -> Any:
    """Render the community hub."""
    db = firestore.client()
    search_term = request.args.get("search", "").strip()

    incoming_requests = UserService.get_user_pending_requests(db, g.user["uid"])
    outgoing_requests = UserService.get_user_sent_requests(db, g.user["uid"])

    data = UserService.get_community_data(db, g.user["uid"], search_term)

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
def users() -> Any:
    """List and allows searching for users."""
    search_term = request.args.get("search", "")
    user_items = UserService.search_users(
        firestore.client(), g.user["uid"], search_term
    )
    return render_template(
        "users.html",
        pagination=MockPagination(user_items),
        search_term=search_term,
        fof=[],
    )


@bp.route("/send_friend_request/<string:friend_id>", methods=["POST"])
@login_required
def send_friend_request(friend_id: str) -> Any:
    """Send a friend request."""
    if g.user["uid"] == friend_id:
        flash(USER_MESSAGES["FRIEND_REQ_SELF"], "danger")
        return redirect(url_for(".users"))

    success = UserService.send_friend_request(
        firestore.client(), g.user["uid"], friend_id
    )
    if success:
        flash(USER_MESSAGES["FRIEND_REQ_SENT"], "success")
    else:
        flash(USER_MESSAGES["FRIEND_REQ_ERROR"], "danger")

    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return jsonify({"success": success})
    return redirect(url_for(".users"))


@bp.route("/friends")
@login_required
def friends() -> Any:
    """Deprecated: Redirects to the community hub."""
    return redirect(url_for(".view_community"))


@bp.route("/requests", methods=["GET"])
@login_required
def friend_requests() -> Any:
    """Deprecated: Redirects to the community hub."""
    return redirect(url_for(".view_community"))


@bp.route("/requests/<string:requester_id>/accept", methods=["POST"])
@bp.route("/accept_friend_request/<string:requester_id>", methods=["POST"])
@login_required
def accept_request(requester_id: str) -> Any:
    """Accept a friend request."""
    db = firestore.client()
    requester = UserService.get_user_by_id(db, requester_id)
    name = UserService.smart_display_name(requester) if requester else "the user"

    if UserService.accept_friend_request(db, g.user["uid"], requester_id):
        flash(USER_MESSAGES["FRIENDS_NOW"].format(name=name), "success")
    else:
        flash(COMMON_MESSAGES["GENERIC_ERROR_SIMPLE"], "danger")

    return redirect(request.referrer or url_for(".view_community"))


@bp.route("/requests/<string:target_id>/cancel", methods=["POST"])
@bp.route("/decline_friend_request/<string:target_id>", methods=["POST"])
@login_required
def cancel_request(target_id: str) -> Any:
    """Cancel or decline a friend request."""
    if UserService.cancel_friend_request(firestore.client(), g.user["uid"], target_id):
        flash(USER_MESSAGES["FRIEND_REQ_PROCESSED"], "success")
    else:
        flash(COMMON_MESSAGES["GENERIC_ERROR_SIMPLE"], "danger")
    return redirect(request.referrer or url_for(".view_community"))


@bp.route("/api/dashboard")
@login_required
def api_dashboard() -> Any:
    """Provide dashboard data as JSON."""
    user_id = g.user["uid"]
    # The JSON API should probably still include everything for backwards compatibility
    # and because it's usually used by clients that expect a full payload.
    data = UserService.get_dashboard_data(
        firestore.client(), user_id, include_activity=True
    )
    streak = data["stats"]["current_streak"]
    s_type = data["stats"]["streak_type"]
    return jsonify(
        {
            "user": UserService.get_user_by_id(firestore.client(), user_id),
            "friends": data["friends"],
            "requests": data["requests"],
            "matches": [
                dict(m) if not isinstance(m, dict) else m for m in data["matches"]
            ],
            "next_cursor": data.get("next_cursor"),
            "group_rankings": data["group_rankings"],
            "stats": {
                "total_matches": data["stats"]["total_games"],
                "win_percentage": data["stats"]["win_rate"],
                "current_streak": f"{streak}{s_type}" if data["matches"] else "N/A",
            },
        }
    )


@bp.route("/api/create_invite", methods=["POST"])
@login_required
def create_invite() -> Any:
    """Generate a unique invite token."""
    token = UserService.create_invite_token(firestore.client(), g.user["uid"])
    return jsonify({"token": token})


@bp.route("/api/search")
@login_required
def api_search_users() -> Any:
    """Search for users and return JSON."""
    search_term = request.args.get("q", "")
    db = firestore.client()
    users = UserService.search_users(db, g.user["uid"], search_term)
    results = []
    for user_data, _, _ in users:
        results.append(
            {
                "id": user_data["id"],
                "name": UserService.smart_display_name(user_data),
                "avatar": user_data.get("profilePictureUrl")
                or url_for("static", filename="user_icon.png"),
            }
        )
    return jsonify(results)
