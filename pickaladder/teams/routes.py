"""Routes for the teams blueprint."""

from firebase_admin import firestore
from flask import flash, g, redirect, render_template, url_for

from pickaladder.auth.decorators import login_required

from . import bp
from .forms import RenameTeamForm


@bp.route("/<string:team_id>")
@login_required
def view_team(team_id):
    """Display a single team's page."""
    db = firestore.client()
    team_ref = db.collection("teams").document(team_id)
    team = team_ref.get()

    if not team.exists:
        flash("Team not found.", "danger")
        return redirect(url_for("group.view_groups"))

    team_data = team.to_dict()
    team_data["id"] = team.id

    # Fetch members' data
    member_refs = team_data.get("members", [])
    members = []
    if member_refs:
        member_snapshots = db.get_all(member_refs)
        for snapshot in member_snapshots:
            if snapshot.exists:
                data = snapshot.to_dict()
                data["id"] = snapshot.id
                members.append(data)

    # Fetch recent matches involving this team
    matches_ref = db.collection("matches")
    query1 = (
        matches_ref.where(filter=firestore.FieldFilter("team1Id", "==", team_id))
        .order_by("matchDate", direction=firestore.Query.DESCENDING)
        .limit(20)
    )
    query2 = (
        matches_ref.where(filter=firestore.FieldFilter("team2Id", "==", team_id))
        .order_by("matchDate", direction=firestore.Query.DESCENDING)
        .limit(20)
    )

    docs1 = list(query1.stream())
    docs2 = list(query2.stream())

    # Combine, remove duplicates, sort, and limit
    all_docs = {doc.id: doc for doc in docs1 + docs2}
    sorted_docs = sorted(
        all_docs.values(),
        key=lambda doc: doc.to_dict().get("matchDate", firestore.SERVER_TIMESTAMP),
        reverse=True,
    )
    recent_matches_docs = sorted_docs[:20]

    # Batch fetch details for all opponent teams
    opponent_team_ids = set()
    for match_doc in recent_matches_docs:
        match_data = match_doc.to_dict()
        if match_data.get("team1Id") == team_id:
            opponent_team_ids.add(match_data.get("team2Id"))
        else:
            opponent_team_ids.add(match_data.get("team1Id"))
    opponent_team_ids.discard(None)

    teams_map = {}
    if opponent_team_ids:
        id_list = list(opponent_team_ids)
        for i in range(0, len(id_list), 30):
            chunk = id_list[i : i + 30]
            team_docs = (
                db.collection("teams")
                .where(filter=firestore.FieldFilter("__name__", "in", chunk))
                .stream()
            )
            for doc in team_docs:
                teams_map[doc.id] = doc.to_dict()

    # Process matches for display
    recent_matches = []
    for match_doc in recent_matches_docs:
        match_data = match_doc.to_dict()
        match_data["id"] = match_doc.id

        opponent_id = (
            match_data.get("team2Id")
            if match_data.get("team1Id") == team_id
            else match_data.get("team1Id")
        )
        opponent_team = teams_map.get(opponent_id, {"name": "Unknown Team"})
        opponent_team["id"] = opponent_id
        match_data["opponent"] = opponent_team

        recent_matches.append(match_data)

    # Calculate aggregate stats
    stats = team_data.get("stats", {})
    wins = stats.get("wins", 0)
    losses = stats.get("losses", 0)
    total_games = wins + losses
    win_percentage = (wins / total_games) * 100 if total_games > 0 else 0

    # Calculate streak from sorted matches (newest to oldest)
    streak = 0
    streak_type = None
    if recent_matches:
        last_match = recent_matches[0]
        winner = last_match.get("winner")
        is_team1 = last_match.get("team1Id") == team_id
        if (winner == "team1" and is_team1) or (winner == "team2" and not is_team1):
            streak_type = "W"
        else:
            streak_type = "L"

        for match in recent_matches:
            winner = match.get("winner")
            is_team1 = match.get("team1Id") == team_id
            current_match_type = (
                "W"
                if (winner == "team1" and is_team1)
                or (winner == "team2" and not is_team1)
                else "L"
            )
            if current_match_type == streak_type:
                streak += 1
            else:
                break

    return render_template(
        "team/view.html",
        team=team_data,
        members=members,
        recent_matches=recent_matches,
        win_percentage=win_percentage,
        streak=streak,
        streak_type=streak_type,
    )


@bp.route("/<string:team_id>/rename", methods=["GET", "POST"])
@login_required
def rename_team(team_id):
    """Rename a team."""
    db = firestore.client()
    team_ref = db.collection("teams").document(team_id)
    team = team_ref.get()

    if not team.exists:
        flash("Team not found.", "danger")
        return redirect(url_for("group.view_groups"))

    team_data = team.to_dict()
    team_data["id"] = team.id

    # Authorization check
    if g.user["uid"] not in team_data.get("member_ids", []):
        flash("You do not have permission to rename this team.", "danger")
        return redirect(url_for(".view_team", team_id=team_id))

    form = RenameTeamForm()
    if form.validate_on_submit():
        try:
            team_ref.update({"name": form.name.data})
            flash("Team renamed successfully.", "success")
            return redirect(url_for(".view_team", team_id=team_id))
        except Exception as e:
            flash(f"An unexpected error occurred: {e}", "danger")

    form.name.data = team_data.get("name")
    return render_template("team/rename_team.html", form=form, team=team_data)
