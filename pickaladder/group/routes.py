"""Routes for the group blueprint."""

from __future__ import annotations

import secrets
from typing import Any

from firebase_admin import firestore, storage
from flask import (
    current_app,
    flash,
    g,
    redirect,
    render_template,
    request,
    url_for,
)
from google.cloud.firestore_v1.field_path import FieldPath
from werkzeug.utils import secure_filename

from pickaladder.auth.decorators import login_required
from pickaladder.group.utils import (
    friend_group_members,
    get_group_leaderboard,
    get_leaderboard_trend_data,
    get_random_joke,
    get_user_group_stats,
    send_invite_email_background,
)
from pickaladder.group.utils import (
    get_head_to_head_stats as get_h2h_stats,
)
from pickaladder.user.services import UserService

from . import bp
from .forms import GroupForm, InviteByEmailForm, InviteFriendForm

UPSET_THRESHOLD = 0.25
GUEST_USER = {"username": "Guest", "id": "unknown"}
DOUBLES_TEAM_SIZE = 2


# TODO: Add type hints for Agent clarity
@bp.route("/", methods=["GET"])
@login_required
def view_groups() -> Any:
    """Display the user's groups."""
    db = firestore.client()

    # Get user's groups
    user_ref = db.collection("users").document(g.user["uid"])
    my_groups_query = db.collection("groups").where(
        filter=firestore.FieldFilter("members", "array_contains", user_ref)
    )
    my_group_docs = list(my_groups_query.stream())

    # --- Enrich groups with owner data ---
    owner_refs = [
        group.to_dict().get("ownerRef")
        for group in my_group_docs
        if group.to_dict().get("ownerRef")
    ]
    unique_owner_refs = list({ref for ref in owner_refs if ref})

    owners_data = {}
    if unique_owner_refs:
        owner_docs = db.get_all(unique_owner_refs)
        owners_data = {doc.id: doc.to_dict() for doc in owner_docs if doc.exists}

    # TODO: Add type hints for Agent clarity
    def enrich_group(group_doc: Any) -> dict[str, Any]:
        """Attach owner data and user stats to a group dictionary."""
        group_data: dict[str, Any] = group_doc.to_dict()
        group_id = group_doc.id
        group_data["id"] = group_id

        # Member count
        members = group_data.get("members", [])
        group_data["member_count"] = len(members)

        # Current User's Stats for this group
        leaderboard = get_group_leaderboard(group_id)
        current_user_id = g.user["uid"]
        user_entry = next((p for p in leaderboard if p["id"] == current_user_id), None)

        if user_entry:
            group_data["user_rank"] = leaderboard.index(user_entry) + 1
            group_data["user_record"] = (
                f"{user_entry.get('wins', 0)}W - {user_entry.get('losses', 0)}L"
            )
        else:
            group_data["user_rank"] = "N/A"
            group_data["user_record"] = "0W - 0L"

        owner_ref = group_data.get("ownerRef")
        if owner_ref and owner_ref.id in owners_data:
            group_data["owner"] = owners_data[owner_ref.id]
        else:
            group_data["owner"] = GUEST_USER
        return group_data

    enriched_my_groups = [{"group": enrich_group(doc)} for doc in my_group_docs]

    return render_template(
        "groups.html",
        my_groups=enriched_my_groups,
    )


# TODO: Add type hints for Agent clarity
@bp.route("/<string:group_id>", methods=["GET", "POST"])
@login_required
def view_group(group_id: str) -> Any:
    """Display a single group's page.

    Display a single group's page, including its members, leaderboard, and
    invite form.
    """
    db = firestore.client()
    group_ref = db.collection("groups").document(group_id)
    group = group_ref.get()
    if not group.exists:
        flash("Group not found.", "danger")
        return redirect(url_for(".view_groups"))

    group_data = group.to_dict()
    group_data["id"] = group.id
    current_user_id = g.user["uid"]
    user_ref = db.collection("users").document(current_user_id)

    # Pre-calculate rivalry stats if players are selected via query params
    playerA_id = request.args.get("playerA")
    playerB_id = request.args.get("playerB")
    rivalry_stats = None
    if playerA_id and playerB_id:
        rivalry_stats = get_h2h_stats(group_id, playerA_id, playerB_id)

    # Fetch members' data
    member_refs = group_data.get("members", [])
    member_ids = {ref.id for ref in member_refs}
    members_snapshots = [ref.get() for ref in member_refs]
    members = []
    for snapshot in members_snapshots:
        if snapshot.exists:
            data = snapshot.to_dict()
            data["id"] = snapshot.id
            members.append(data)

    # Fetch owner's data
    owner = None
    owner_ref = group_data.get("ownerRef")
    if owner_ref:
        owner_doc = owner_ref.get()
        if owner_doc.exists:
            owner = owner_doc.to_dict()

    is_member = current_user_id in member_ids
    form = InviteFriendForm()

    # Get user's accepted friends
    friends_query = (
        user_ref.collection("friends")
        .where(filter=firestore.FieldFilter("status", "==", "accepted"))
        .stream()
    )
    friend_ids = {doc.id for doc in friends_query}

    # Find friends who are not already members
    eligible_friend_ids = list(friend_ids - member_ids)

    eligible_friends = []
    if eligible_friend_ids:
        # FieldPath.document_id() must be used when filtering by document IDs
        # with a list of strings to avoid "InvalidArgument: 400 key filter
        # value must be a Key" errors.
        eligible_friends_query = (
            db.collection("users")
            .where(
                filter=firestore.FieldFilter(
                    FieldPath.document_id(), "in", eligible_friend_ids
                )
            )
            .stream()
        )
        eligible_friends = [doc for doc in eligible_friends_query]

    form.friend.choices = [
        (friend.id, friend.to_dict().get("name", friend.id))
        for friend in eligible_friends
    ]

    if response := _process_friend_invite(db, group_id, group_ref, form):
        return response

    # --- Invite by Email Logic ---
    invite_email_form = InviteByEmailForm()
    if response := _process_email_invite(
        db, group_id, group_data, current_user_id, invite_email_form
    ):
        return response

    # --- Fetch and Calculate Data for Display ---
    leaderboard = get_group_leaderboard(group_id)

    # Fetch Match History and Teams
    recent_matches_docs, recent_matches = _fetch_recent_matches(db, group_id)
    team_leaderboard, best_buds = _fetch_group_teams(
        db, group_id, member_ids, recent_matches_docs
    )

    # Fetch Pending Invites
    pending_members = []
    if is_member:
        pending_members = _get_pending_invites(db, group_id)

    return render_template(
        "group.html",
        group=group_data,
        group_id=group.id,
        members=members,
        owner=owner,
        form=form,
        invite_email_form=invite_email_form,
        current_user_id=current_user_id,
        leaderboard=leaderboard,
        pending_members=pending_members,
        is_member=is_member,
        recent_matches=recent_matches,
        best_buds=best_buds,
        team_leaderboard=team_leaderboard,
        rivalry_stats=rivalry_stats,
        playerA_id=playerA_id,
        playerB_id=playerB_id,
    )


# TODO: Add type hints for Agent clarity
@bp.route("/create", methods=["GET", "POST"])
@login_required
def create_group() -> Any:
    """Create a new group."""
    form = GroupForm()
    if form.validate_on_submit():
        db = firestore.client()
        user_ref = db.collection("users").document(g.user["uid"])
        try:
            group_data = {
                "name": form.name.data,
                "description": form.description.data,
                "location": form.location.data,
                "is_public": form.is_public.data,
                "ownerRef": user_ref,
                "members": [user_ref],  # Owner is the first member
                "createdAt": firestore.SERVER_TIMESTAMP,
            }
            timestamp, new_group_ref = db.collection("groups").add(group_data)
            group_id = new_group_ref.id

            profile_picture_file = form.profile_picture.data
            if profile_picture_file:
                try:
                    filename = secure_filename(
                        profile_picture_file.filename or "group_profile.jpg"
                    )
                    bucket = storage.bucket()
                    blob = bucket.blob(f"group_pictures/{group_id}/{filename}")

                    blob.upload_from_file(profile_picture_file)
                    blob.make_public()

                    new_group_ref.update({"profilePictureUrl": blob.public_url})
                except Exception as e:
                    current_app.logger.error(f"Error uploading group image: {e}")
                    flash("Group created, but failed to upload image.", "warning")
                    return redirect(url_for(".view_group", group_id=group_id))

            flash("Group created successfully.", "success")
            return redirect(url_for(".view_group", group_id=group_id))
        except Exception as e:
            flash(f"An unexpected error occurred: {e}", "danger")
    return render_template("create_group.html", form=form)


# TODO: Add type hints for Agent clarity
@bp.route("/<string:group_id>/edit", methods=["GET", "POST"])
@login_required
def edit_group(group_id: str) -> Any:
    """Edit a group."""
    db = firestore.client()
    group_ref = db.collection("groups").document(group_id)
    group = group_ref.get()
    if not group.exists:
        flash("Group not found.", "danger")
        return redirect(url_for(".view_groups"))

    group_data = group.to_dict()
    group_data["id"] = group.id
    owner_ref = group_data.get("ownerRef")
    if not owner_ref or owner_ref.id != g.user["uid"]:
        flash("You do not have permission to edit this group.", "danger")
        return redirect(url_for(".view_group", group_id=group.id))

    form = GroupForm(data=group_data)
    if form.validate_on_submit():
        try:
            update_data = {
                "name": form.name.data,
                "description": form.description.data,
                "location": form.location.data,
                "is_public": form.is_public.data,
            }

            profile_picture_file = form.profile_picture.data
            if profile_picture_file:
                filename = secure_filename(
                    profile_picture_file.filename or "group_profile.jpg"
                )
                bucket = storage.bucket()
                blob = bucket.blob(f"group_pictures/{group_id}/{filename}")

                blob.upload_from_file(profile_picture_file)
                blob.make_public()

                update_data["profilePictureUrl"] = blob.public_url

            group_ref.update(update_data)
            flash("Group updated successfully.", "success")
            return redirect(url_for(".view_group", group_id=group.id))
        except Exception as e:
            flash(f"An unexpected error occurred: {e}", "danger")

    return render_template(
        "edit_group.html", form=form, group=group_data, group_id=group.id
    )


# TODO: Add type hints for Agent clarity
@bp.route("/invite/<token>/resend", methods=["POST"])
@login_required
def resend_invite(token: str) -> Any:
    """Resend a group invitation."""
    db = firestore.client()
    invite_ref = db.collection("group_invites").document(token)
    invite = invite_ref.get()

    if not invite.exists:
        flash("Invite not found", "danger")
        return redirect(url_for("auth.login"))

    data = invite.to_dict()
    group_id = data.get("group_id")

    # Check permissions
    group_ref = db.collection("groups").document(group_id)
    group = group_ref.get()
    if not group.exists:
        flash("Group not found", "danger")
        return redirect(url_for("auth.login"))

    owner_ref = group.to_dict().get("ownerRef")
    if not owner_ref or owner_ref.id != g.user["uid"]:
        flash("Permission denied", "danger")
        return redirect(url_for(".view_group", group_id=group_id))

    new_email = request.form.get("email")
    if new_email:
        data["email"] = new_email
        invite_ref.update({"email": new_email})

    invite_ref.update({"status": "sending"})

    invite_url = url_for(".handle_invite", token=token, _external=True)
    email_data = {
        "to": data.get("email"),
        "subject": f"Join {group.to_dict().get('name')} on pickaladder!",
        "template": "email/group_invite.html",
        "name": data.get("name"),
        "group_name": group.to_dict().get("name"),
        "invite_url": invite_url,
        "joke": get_random_joke(),
    }

    send_invite_email_background(
        current_app._get_current_object(),  # type: ignore[attr-defined]
        token,
        email_data,
    )
    flash(f"Resending invitation to {data.get('email')}...", "toast")
    return redirect(url_for(".view_group", group_id=group_id))


# TODO: Add type hints for Agent clarity
@bp.route("/<string:group_id>/leaderboard-trend")
@login_required
def view_leaderboard_trend(group_id: str) -> Any:
    """Display a trend chart of the group's leaderboard."""
    db = firestore.client()
    group_ref = db.collection("groups").document(group_id)
    group = group_ref.get()
    if not group.exists:
        flash("Group not found.", "danger")
        return redirect(url_for(".view_groups"))

    group_data = group.to_dict()
    group_data["id"] = group.id

    trend_data = get_leaderboard_trend_data(group_id)
    user_stats = get_user_group_stats(group_id, g.user["uid"])

    return render_template(
        "group_leaderboard_trend.html",
        group=group_data,
        trend_data=trend_data,
        user_stats=user_stats,
    )


# TODO: Add type hints for Agent clarity
@bp.route("/invite/<token>/delete", methods=["POST"])
@login_required
def delete_invite(token: str) -> Any:
    """Delete a pending invitation."""
    db = firestore.client()
    invite_ref = db.collection("group_invites").document(token)
    invite = invite_ref.get()

    if not invite.exists:
        flash("Invite not found", "danger")
        return redirect(url_for("auth.login"))

    group_id = invite.to_dict().get("group_id")
    group_ref = db.collection("groups").document(group_id)
    group = group_ref.get()

    if not group.exists:
        flash("Group not found", "danger")
        return redirect(url_for("auth.login"))

    owner_ref = group.to_dict().get("ownerRef")
    if not owner_ref or owner_ref.id != g.user["uid"]:
        flash("Permission denied", "danger")
        return redirect(url_for(".view_group", group_id=group_id))

    invite_ref.delete()
    flash("Invitation removed.", "success")
    return redirect(url_for(".view_group", group_id=group_id))


# TODO: Add type hints for Agent clarity
@bp.route("/invite/<token>")
@login_required
def handle_invite(token: str) -> Any:
    """Handle an invitation link."""
    db = firestore.client()
    invite_ref = db.collection("group_invites").document(token)
    invite = invite_ref.get()

    if not invite.exists:
        flash("Invalid invitation link.", "danger")
        return redirect(url_for("auth.login"))

    invite_data = invite.to_dict()
    if invite_data.get("used"):
        flash("This invitation has already been used.", "warning")
        return redirect(url_for("auth.login"))

    group_id = invite_data.get("group_id")
    group_ref = db.collection("groups").document(group_id)
    user_ref = db.collection("users").document(g.user["uid"])

    try:
        # Merge ghost user if exists
        invite_email = invite_data.get("email")
        if invite_email:
            UserService.merge_ghost_user(db, user_ref, invite_email)

        # Add user to group
        group_ref.update({"members": firestore.ArrayUnion([user_ref])})
        # Mark invite as used
        invite_ref.update({"used": True, "used_by": g.user["uid"]})

        # Friend other group members
        friend_group_members(db, group_id, user_ref)

        flash("Welcome to the team!", "success")
        return redirect(url_for(".view_group", group_id=group_id))
    except Exception as e:
        flash(f"An error occurred while joining the group: {e}", "danger")
        return redirect(url_for("auth.login"))


# TODO: Add type hints for Agent clarity
@bp.route("/<string:group_id>/delete", methods=["POST"])
@login_required
def delete_group(group_id: str) -> Any:
    """Delete a group."""
    db = firestore.client()
    group_ref = db.collection("groups").document(group_id)
    group = group_ref.get()
    if not group.exists:
        flash("Group not found.", "danger")
        return redirect(url_for(".view_groups"))

    group_data = group.to_dict()
    owner_ref = group_data.get("ownerRef")
    if not owner_ref or owner_ref.id != g.user["uid"]:
        flash("You do not have permission to delete this group.", "danger")
        return redirect(url_for(".view_group", group_id=group.id))

    try:
        group_ref.delete()
        flash("Group deleted successfully.", "success")
        return redirect(url_for(".view_groups"))
    except Exception as e:
        flash(f"An unexpected error occurred: {e}", "danger")
        return redirect(url_for(".view_group", group_id=group.id))


# TODO: Add type hints for Agent clarity
@bp.route("/<string:group_id>/join", methods=["POST"])
@login_required
def join_group(group_id: str) -> Any:
    """Join a group."""
    db = firestore.client()
    group_ref = db.collection("groups").document(group_id)
    user_ref = db.collection("users").document(g.user["uid"])

    try:
        group_ref.update({"members": firestore.ArrayUnion([user_ref])})
        friend_group_members(db, group_id, user_ref)
        flash("Successfully joined the group.", "success")
    except Exception as e:
        flash(f"An error occurred while trying to join the group: {e}", "danger")

    return redirect(url_for(".view_group", group_id=group_id))


# TODO: Add type hints for Agent clarity
@bp.route("/<string:group_id>/leave", methods=["POST"])
@login_required
def leave_group(group_id: str) -> Any:
    """Leave a group."""
    db = firestore.client()
    group_ref = db.collection("groups").document(group_id)
    user_ref = db.collection("users").document(g.user["uid"])

    try:
        group_ref.update({"members": firestore.ArrayRemove([user_ref])})
        flash("You have left the group.", "success")
    except Exception as e:
        flash(f"An error occurred while trying to leave the group: {e}", "danger")

    return redirect(url_for(".view_group", group_id=group_id))


# TODO: Add type hints for Agent clarity
@bp.route("/<string:group_id>/stats/rivalry", methods=["GET"])
@login_required
def get_rivalry_stats(group_id: str) -> Any:
    """Return head-to-head stats for two players in a group."""
    playerA_id = request.args.get("playerA_id")
    playerB_id = request.args.get("playerB_id")

    if not playerA_id or not playerB_id:
        return {"error": "playerA_id and playerB_id are required"}, 400

    stats = get_h2h_stats(group_id, playerA_id, playerB_id)

    return {
        "wins": stats["wins"],
        "losses": stats["losses"],
        "matches": stats["matches"],
        "point_diff": stats["point_diff"],
        "avg_points_scored": stats["avg_points_scored"],
        "partnership_record": stats["partnership_record"],
    }


def _fetch_recent_matches(
    db: Any, group_id: str
) -> tuple[list[Any], list[dict[str, Any]]]:
    """Fetch and enrich recent matches for a group."""
    matches_ref = db.collection("matches")
    matches_query = (
        matches_ref.where(filter=firestore.FieldFilter("groupId", "==", group_id))
        .order_by("matchDate", direction=firestore.Query.DESCENDING)
        .limit(20)
    )
    recent_matches_docs = list(matches_query.stream())

    # Collect and fetch associated entities
    team_refs, player_refs = _collect_refs_from_matches(recent_matches_docs)
    teams_map = _batch_fetch_entities(db, team_refs)
    players_map = _batch_fetch_entities(db, player_refs)

    # Enrich match data
    recent_matches = []
    for match_doc in recent_matches_docs:
        match_data = _enrich_single_match(match_doc, teams_map, players_map)
        recent_matches.append(match_data)

    _calculate_giant_slayer_upsets(recent_matches)

    return recent_matches_docs, recent_matches


def _collect_refs_from_matches(
    matches_docs: list[Any],
) -> tuple[list[Any], list[Any]]:
    """Extract team and player references from match documents."""
    team_refs = []
    player_refs = []
    player_keys = [
        "player1Ref",
        "player2Ref",
        "partnerRef",
        "opponent1Ref",
        "opponent2Ref",
        "player1",
        "player2",
        "partner",
        "opponent1",
        "opponent2",
    ]

    for doc in matches_docs:
        data = doc.to_dict()
        for field in ["team1Ref", "team2Ref"]:
            if (ref := data.get(field)) and isinstance(
                ref, firestore.DocumentReference
            ):
                team_refs.append(ref)

        for key in player_keys:
            if (ref := data.get(key)) and isinstance(ref, firestore.DocumentReference):
                player_refs.append(ref)

    return team_refs, player_refs


def _batch_fetch_entities(db: Any, refs: list[Any]) -> dict[str, Any]:
    """Batch fetch multiple Firestore documents and return a map by ID."""
    if not refs:
        return {}

    # Deduplicate by path
    unique_refs = list({ref.path: ref for ref in refs if hasattr(ref, "path")}.values())
    if not unique_refs:
        return {}

    docs = db.get_all(unique_refs)
    return {doc.id: {**doc.to_dict(), "id": doc.id} for doc in docs if doc.exists}


def _enrich_single_match(
    match_doc: Any, teams_map: dict[str, Any], players_map: dict[str, Any]
) -> dict[str, Any]:
    """Attach team and player data to a single match dictionary."""
    match_data = match_doc.to_dict()
    match_data["id"] = match_doc.id

    # Attach Teams
    for field in ["team1", "team2"]:
        if (ref := match_data.get(f"{field}Ref")) and isinstance(
            ref, firestore.DocumentReference
        ):
            match_data[field] = teams_map.get(ref.id)

    # Attach Players
    player_keys = [
        "player1",
        "player2",
        "partner",
        "opponent1",
        "opponent2",
        "player1Ref",
        "player2Ref",
        "partnerRef",
        "opponent1Ref",
        "opponent2Ref",
    ]
    for key in player_keys:
        ref = match_data.get(key)
        if isinstance(ref, firestore.DocumentReference):
            target = key.replace("Ref", "")
            match_data[target] = players_map.get(ref.id, GUEST_USER)

    return match_data


def _calculate_giant_slayer_upsets(recent_matches: list[dict[str, Any]]) -> None:
    """Identify 'giant slayer' upsets based on DUPR rating gaps."""
    for match_data in recent_matches:
        winner_player = None
        loser_player = None
        if match_data.get("winner") == "team1":
            winner_player = match_data.get("player1")
            loser_player = match_data.get("player2")
        elif match_data.get("winner") == "team2":
            winner_player = match_data.get("player2")
            loser_player = match_data.get("player1")

        if winner_player and loser_player:
            winner_rating = float(winner_player.get("dupr_rating") or 0.0)
            loser_rating = float(loser_player.get("dupr_rating") or 0.0)
            if loser_rating > 0 and winner_rating > 0:
                if (loser_rating - winner_rating) >= UPSET_THRESHOLD:
                    match_data["is_upset"] = True


def _fetch_group_teams(
    db: Any, group_id: str, member_ids: set[str], recent_matches_docs: list[Any]
) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    """Calculate team leaderboard and best buds for a group."""
    team_stats = _calculate_team_stats(recent_matches_docs)
    if not team_stats:
        return [], None

    team_ids = list(team_stats.keys())
    team_refs = [db.collection("teams").document(tid) for tid in team_ids]
    team_docs = db.get_all(team_refs)

    # Batch fetch all team member details
    all_member_refs = []
    enriched_team_docs = []
    for doc in team_docs:
        if doc.exists:
            team_data = {**doc.to_dict(), "id": doc.id}
            all_member_refs.extend(team_data.get("members", []))
            enriched_team_docs.append(team_data)

    members_map = _batch_fetch_entities(db, all_member_refs)

    team_leaderboard = []
    for team_data in enriched_team_docs:
        stats = team_stats[team_data["id"]]
        stats["win_percentage"] = (
            (stats["wins"] / stats["games"]) * 100 if stats["games"] > 0 else 0
        )

        team_data["member_details"] = [
            members_map[m.id]
            for m in team_data.get("members", [])
            if m.id in members_map
        ]
        team_leaderboard.append({"team": team_data, "stats": stats})

    team_leaderboard.sort(key=lambda x: x["stats"]["wins"], reverse=True)
    best_buds = _extract_best_buds(team_leaderboard)

    return team_leaderboard, best_buds


def _calculate_team_stats(recent_matches_docs: list[Any]) -> dict[str, Any]:
    """Aggregate wins/losses per team from match history."""
    stats = {}
    for doc in recent_matches_docs:
        data = doc.to_dict()
        if data.get("matchType") != "doubles":
            continue

        t1_id = data.get("team1Ref").id if data.get("team1Ref") else None
        t2_id = data.get("team2Ref").id if data.get("team2Ref") else None
        if not t1_id or not t2_id:
            continue

        for tid in [t1_id, t2_id]:
            if tid not in stats:
                stats[tid] = {"wins": 0, "losses": 0, "games": 0}

        p1_score = data.get("player1Score", data.get("team1Score", 0))
        p2_score = data.get("player2Score", data.get("team2Score", 0))

        stats[t1_id]["games"] += 1
        stats[t2_id]["games"] += 1

        if p1_score > p2_score:
            stats[t1_id]["wins"] += 1
            stats[t2_id]["losses"] += 1
        elif p2_score > p1_score:
            stats[t2_id]["wins"] += 1
            stats[t1_id]["losses"] += 1
    return stats


def _extract_best_buds(team_leaderboard: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Identify the top-performing team for the 'Best Buds' feature."""
    if not team_leaderboard:
        return None
    top_team = team_leaderboard[0]
    if top_team["stats"]["wins"] > 0:
        best_buds = top_team["team"].copy()
        best_buds["stats"] = top_team["stats"]
        return best_buds
    return None


def _get_pending_invites(db: Any, group_id: str) -> list[dict[str, Any]]:
    """Fetch pending invites for a group."""
    pending_members = []
    invites_ref = db.collection("group_invites")
    query = invites_ref.where(
        filter=firestore.FieldFilter("group_id", "==", group_id)
    ).where(filter=firestore.FieldFilter("used", "==", False))

    pending_invites_docs = list(query.stream())
    for doc in pending_invites_docs:
        data = doc.to_dict()
        data["token"] = doc.id
        pending_members.append(data)

    # Enrich invites with user data
    invite_emails = [
        invite.get("email") for invite in pending_members if invite.get("email")
    ]
    if invite_emails:
        user_docs = {}
        # Chunk the email list to handle Firestore's 30-item limit for 'in' queries
        for i in range(0, len(invite_emails), 30):
            chunk = invite_emails[i : i + 30]
            users_ref = db.collection("users")
            user_query = users_ref.where(
                filter=firestore.FieldFilter("email", "in", chunk)
            )
            for doc in user_query.stream():
                user_docs[doc.to_dict()["email"]] = doc.to_dict()

        for invite in pending_members:
            user_data = user_docs.get(invite.get("email"))
            if user_data:
                invite["username"] = user_data.get("username", invite.get("name"))
                invite["profilePictureUrl"] = user_data.get("profilePictureUrl")

    # Sort in memory to avoid composite index requirement
    pending_members.sort(key=lambda x: x.get("created_at") or 0, reverse=True)
    return pending_members


def _process_friend_invite(db: Any, group_id: str, group_ref: Any, form: Any) -> Any:
    """Handle friend invitation submission."""
    if form.validate_on_submit() and "friend" in request.form:
        friend_id = form.friend.data
        friend_ref = db.collection("users").document(friend_id)
        try:
            group_ref.update({"members": firestore.ArrayUnion([friend_ref])})
            flash("Friend invited successfully.", "success")
            return redirect(url_for(".view_group", group_id=group_id))
        except Exception as e:
            flash(f"An unexpected error occurred: {e}", "danger")
    return None


def _process_email_invite(
    db: Any,
    group_id: str,
    group_data: dict[str, Any],
    current_user_id: str,
    invite_email_form: Any,
) -> Any:
    """Handle email invitation submission."""
    if invite_email_form.validate_on_submit() and "email" in request.form:
        try:
            name = invite_email_form.name.data or "Friend"
            original_email: str = invite_email_form.email.data or ""
            email = original_email.lower()

            # Check if user exists
            users_ref = db.collection("users")
            existing_user = None

            # 1. Check lowercase
            query_lower = users_ref.where(
                filter=firestore.FieldFilter("email", "==", email)
            ).limit(1)
            docs = list(query_lower.stream())

            if docs:
                existing_user = docs[0]
            # 2. Check original if different
            elif original_email != email:
                query_orig = users_ref.where(
                    filter=firestore.FieldFilter("email", "==", original_email)
                ).limit(1)
                docs = list(query_orig.stream())
                if docs:
                    existing_user = docs[0]

            if existing_user:
                invite_email = existing_user.to_dict().get("email")
            else:
                invite_email = email
                ghost_user_data = {
                    "email": email,
                    "name": name,
                    "is_ghost": True,
                    "createdAt": firestore.SERVER_TIMESTAMP,
                    "username": f"ghost_{secrets.token_hex(4)}",
                }
                db.collection("users").add(ghost_user_data)

            token = secrets.token_urlsafe(32)
            invite_data = {
                "group_id": group_id,
                "email": invite_email,
                "name": name,
                "inviter_id": current_user_id,
                "created_at": firestore.SERVER_TIMESTAMP,
                "used": False,
                "status": "sending",
            }
            db.collection("group_invites").document(token).set(invite_data)

            invite_url = url_for(".handle_invite", token=token, _external=True)
            email_data = {
                "to": email,
                "subject": f"Join {group_data.get('name')} on pickaladder!",
                "template": "email/group_invite.html",
                "name": name,
                "group_name": group_data.get("name"),
                "invite_url": invite_url,
                "joke": get_random_joke(),
            }

            send_invite_email_background(
                current_app._get_current_object(),  # type: ignore[attr-defined]
                token,
                email_data,
            )

            flash(f"Invitation is being sent to {email}.", "toast")
            return redirect(url_for(".view_group", group_id=group_id))
        except Exception as e:
            flash(f"An error occurred creating the invitation: {e}", "danger")
    return None
