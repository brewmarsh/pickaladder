"""Business logic for group-related operations."""

import operator
import secrets
import sys
import threading
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from firebase_admin import firestore
from google.cloud.firestore import (
    Client,
    DocumentReference,
    DocumentSnapshot,
    FieldFilter,
)

from pickaladder.constants import DOUBLES_TEAM_SIZE
from pickaladder.utils import send_email

GUEST_USER = {"username": "Guest", "id": "unknown"}
UPSET_THRESHOLD = 0.25
RECENT_MATCHES_LIMIT = 5
HOT_STREAK_THRESHOLD = 3
FIRESTORE_BATCH_LIMIT = 400


def get_random_joke() -> str:
    """Return a random sport/dad joke."""
    jokes = [
        "Why did the pickleball player get arrested? Because he was caught smashing!",
        "What do you call a girl standing in the middle of a tennis court? Annette.",
        (
            "Why are fish never good at tennis? Because they don't like getting "
            "close to the net."
        ),
        "What is a tennis player's favorite city? Volley-wood.",
        "Why do tennis players never get married? Because love means nothing to them.",
        "What time does a tennis player go to bed? Ten-ish.",
        (
            "Why did the pickleball hit the net? It wanted to see what was on the "
            "other side."
        ),
        "How is a pickleball game like a waiter? They both serve.",
        (
            "Why should you never fall in love with a tennis player? To them, 'Love' "
            "means nothing."
        ),
        "What do you serve but not eat? A tennis ball.",
    ]
    return secrets.choice(jokes)


def get_group_details(
    db: firestore.Client, group_id: str, current_user_id: str
) -> Optional[dict[str, Any]]:
    """
    Fetch all details for a group page.
    Fetches all details for a group page, including members, leaderboards,
    matches, and invites.
    """
    group_ref = db.collection("groups").document(group_id)
    group = group_ref.get()
    if not group.exists:
        return None

    group_data = group.to_dict()
    group_data["id"] = group.id

    # Fetch members and owner
    member_refs = group_data.get("members", [])
    member_ids = {ref.id for ref in member_refs}
    members_snapshots = [ref.get() for ref in member_refs]
    members = []
    for snapshot in members_snapshots:
        if snapshot.exists:
            data = snapshot.to_dict()
            data["id"] = snapshot.id
            members.append(data)

    owner = None
    owner_ref = group_data.get("ownerRef")
    if owner_ref:
        owner_doc = owner_ref.get()
        if owner_doc.exists:
            owner = owner_doc.to_dict()

    is_member = current_user_id in member_ids

    # Team Leaderboard
    team_leaderboard = _get_team_leaderboard(db, member_ids)

    # Pending Invites
    pending_members = []
    if is_member:
        pending_members = _get_pending_invites(db, group_id)

    # Fetch recent matches and all players involved
    (
        recent_matches_docs,
        users_map,
        teams_map,
    ) = _get_recent_matches_and_players(db, group_id)

    # Best Buds calculation using all group matches
    best_buds = _calculate_best_buds(db, group_id)

    # Enrich matches with player data and upset status
    enriched_matches = _enrich_matches(recent_matches_docs, users_map, teams_map)

    # Singles Leaderboard
    leaderboard = get_group_leaderboard(db, group_id)

    return {
        "group_data": group_data,
        "members": members,
        "owner": owner,
        "is_member": is_member,
        "team_leaderboard": team_leaderboard,
        "pending_members": pending_members,
        "recent_matches": enriched_matches,
        "best_buds": best_buds,
        "leaderboard": leaderboard,
    }


def _get_id(data: dict[str, Any], possible_keys: list[str]) -> Optional[str]:
    """Get first non-None value for a list of possible keys."""
    for key in possible_keys:
        if key in data and data[key] is not None:
            return data[key]
    return None


def _calculate_leaderboard_from_matches(
    member_refs: list[DocumentReference], matches: list[DocumentSnapshot]
) -> list[dict[str, Any]]:
    """Calculate the leaderboard from a list of matches."""
    player_stats = {
        ref.id: {
            "wins": 0,
            "losses": 0,
            "games": 0,
            "total_score": 0,
            "user_data": ref.get(),
            "last_matches": [],  # For form calculation
        }
        for ref in member_refs
    }

    # Helper function to update stats
    def update_player_stats(
        player_id: str, score: int, is_winner: bool, is_draw: bool = False
    ):
        """Update player statistics."""
        if player_id in player_stats:
            player_stats[player_id]["games"] += 1
            player_stats[player_id]["total_score"] += score
            if is_winner:
                player_stats[player_id]["wins"] += 1
            elif not is_draw:
                player_stats[player_id]["losses"] += 1

    # Sort matches by date descending to get recent matches first
    matches.sort(
        key=lambda m: m.to_dict().get("matchDate") or datetime.min, reverse=True
    )

    for match in matches:
        data = match.to_dict()
        match_type = data.get("matchType", "singles")
        p1_score = data.get("player1Score", 0)
        p2_score = data.get("player2Score", 0)

        p1_wins = p1_score > p2_score
        p2_wins = p2_score > p1_score
        is_draw = p1_score == p2_score

        # Store match result for form calculation
        if match_type == "doubles":
            for ref in data.get("team1", []):
                if (
                    ref.id in player_stats
                    and len(player_stats[ref.id]["last_matches"]) < RECENT_MATCHES_LIMIT
                ):
                    player_stats[ref.id]["last_matches"].append(
                        "win" if p1_wins else "loss"
                    )
            for ref in data.get("team2", []):
                if (
                    ref.id in player_stats
                    and len(player_stats[ref.id]["last_matches"]) < RECENT_MATCHES_LIMIT
                ):
                    player_stats[ref.id]["last_matches"].append(
                        "win" if p2_wins else "loss"
                    )
        else:
            p1_ref, p2_ref = data.get("player1Ref"), data.get("player2Ref")
            if (
                p1_ref
                and p1_ref.id in player_stats
                and len(player_stats[p1_ref.id]["last_matches"]) < RECENT_MATCHES_LIMIT
            ):
                player_stats[p1_ref.id]["last_matches"].append(
                    "win" if p1_wins else "loss"
                )
            if (
                p2_ref
                and p2_ref.id in player_stats
                and len(player_stats[p2_ref.id]["last_matches"]) < RECENT_MATCHES_LIMIT
            ):
                player_stats[p2_ref.id]["last_matches"].append(
                    "win" if p2_wins else "loss"
                )

        if match_type == "doubles":
            for ref in data.get("team1", []):
                update_player_stats(ref.id, p1_score, p1_wins, is_draw)
            for ref in data.get("team2", []):
                update_player_stats(ref.id, p2_score, p2_wins, is_draw)
        else:
            p1_ref = data.get("player1Ref")
            p2_ref = data.get("player2Ref")
            if p1_ref:
                update_player_stats(p1_ref.id, p1_score, p1_wins, is_draw)
            if p2_ref:
                update_player_stats(p2_ref.id, p2_score, p2_wins, is_draw)

    leaderboard = []
    for user_id, stats in player_stats.items():
        user_doc = stats["user_data"]
        if not user_doc.exists:
            continue

        user_data = user_doc.to_dict()
        games_played = stats["games"]
        avg_score = stats["total_score"] / games_played if games_played > 0 else 0.0
        leaderboard.append(
            {
                "id": user_id,
                "name": user_data.get("name", "N/A"),
                "wins": stats["wins"],
                "losses": stats["losses"],
                "games_played": stats["games"],
                "avg_score": avg_score,
                "form": stats.get("last_matches", []),
            }
        )
    leaderboard.sort(
        key=operator.itemgetter("avg_score", "wins", "games_played"), reverse=True
    )
    return leaderboard


def get_group_leaderboard(db: Client, group_id: str) -> list[dict[str, Any]]:
    """Calculate the leaderboard for a specific group."""
    group_ref = db.collection("groups").document(group_id)
    group = group_ref.get()
    if not group.exists:
        return []

    group_data = group.to_dict()
    member_refs = group_data.get("members", [])
    if not member_refs:
        return []

    all_matches_stream = (
        db.collection("matches")
        .where(filter=FieldFilter("groupId", "==", group_id))
        .stream()
    )
    all_matches = list(all_matches_stream)

    current_leaderboard = _calculate_leaderboard_from_matches(member_refs, all_matches)

    one_week_ago = datetime.now(timezone.utc) - timedelta(days=7)
    matches_last_week = [
        m
        for m in all_matches
        if m.to_dict().get("matchDate") and m.to_dict().get("matchDate") < one_week_ago
    ]

    last_week_leaderboard = _calculate_leaderboard_from_matches(
        member_refs, matches_last_week
    )
    last_week_ranks = {
        player["id"]: i + 1 for i, player in enumerate(last_week_leaderboard)
    }

    for i, player in enumerate(current_leaderboard):
        current_rank = i + 1
        last_week_rank = last_week_ranks.get(player["id"])
        if last_week_rank is not None:
            player["rank_change"] = last_week_rank - current_rank
        else:
            player["rank_change"] = "new"

    all_matches.sort(
        key=lambda m: m.to_dict().get("matchDate") or datetime.min, reverse=True
    )

    user_matches_map: dict[str, list[dict[str, Any]]] = {
        ref.id: [] for ref in member_refs
    }
    for match in all_matches:
        data = match.to_dict()
        match_type = data.get("matchType", "singles")
        if match_type == "doubles":
            for ref in data.get("team1", []):
                if ref.id in user_matches_map:
                    user_matches_map[ref.id].append(data)
            for ref in data.get("team2", []):
                if ref.id in user_matches_map:
                    user_matches_map[ref.id].append(data)
        else:
            p1_ref, p2_ref = data.get("player1Ref"), data.get("player2Ref")
            if p1_ref and p1_ref.id in user_matches_map:
                user_matches_map[p1_ref.id].append(data)
            if p2_ref and p2_ref.id in user_matches_map:
                user_matches_map[p2_ref.id].append(data)

    for player in current_leaderboard:
        streak = 0
        user_id = player["id"]
        for match_data in user_matches_map.get(user_id, []):
            p1_score = match_data.get("player1Score", 0)
            p2_score = match_data.get("player2Score", 0)
            p1_wins = p1_score > p2_score
            p2_wins = p2_score > p1_score
            is_draw = p1_score == p2_score

            if is_draw:
                break

            user_won = False
            match_type = match_data.get("matchType", "singles")
            if match_type == "doubles":
                team1_ids = [ref.id for ref in match_data.get("team1", [])]
                team2_ids = [ref.id for ref in match_data.get("team2", [])]
                if user_id in team1_ids:
                    if p1_wins:
                        user_won = True
                elif user_id in team2_ids:
                    if p2_wins:
                        user_won = True
            else:
                p1_ref, p2_ref = (
                    match_data.get("player1Ref"),
                    match_data.get("player2Ref"),
                )
                if p1_ref and p1_ref.id == user_id:
                    if p1_wins:
                        user_won = True
                elif p2_ref and p2_ref.id == user_id:
                    if p2_wins:
                        user_won = True

            if user_won:
                streak += 1
            else:
                break

        player["streak"] = streak
        player["is_on_fire"] = streak >= HOT_STREAK_THRESHOLD

    return current_leaderboard


def get_leaderboard_trend_data(db: Client, group_id: str) -> dict[str, Any]:
    """Generate data for a leaderboard trend chart."""
    matches_query = db.collection("matches").where(
        filter=FieldFilter("groupId", "==", group_id)
    )
    matches = [m for m in matches_query.stream() if m.to_dict().get("matchDate")]
    matches.sort(key=lambda x: x.to_dict().get("matchDate"))
    if not matches:
        return {"labels": [], "datasets": []}

    all_player_refs = set()
    for match in matches:
        data = match.to_dict()
        if data.get("matchType", "singles") == "doubles":
            all_player_refs.update(data.get("team1", []))
            all_player_refs.update(data.get("team2", []))
        else:
            if data.get("player1Ref"):
                all_player_refs.add(data.get("player1Ref"))
            if data.get("player2Ref"):
                all_player_refs.add(data.get("player2Ref"))

    player_docs = db.get_all(list(all_player_refs))
    players_data = {}
    for doc in player_docs:
        if doc.exists:
            data = doc.to_dict()
            players_data[doc.id] = {
                "name": data.get("name", "Unknown"),
                "profilePictureUrl": data.get("profilePictureUrl"),
            }

    player_stats = {ref.id: {"total_score": 0, "games": 0} for ref in all_player_refs}
    trend_data: dict[str, Any] = {"labels": [], "datasets": {}}

    for player_id, player_info in players_data.items():
        trend_data["datasets"][player_id] = {
            "label": player_info["name"],
            "data": [],
            "fill": False,
            "profilePictureUrl": player_info["profilePictureUrl"],
        }

    unique_dates = sorted(
        list({m.to_dict().get("matchDate").strftime("%Y-%m-%d") for m in matches})
    )
    trend_data["labels"] = unique_dates

    date_idx = 0
    for i, match in enumerate(matches):
        data = match.to_dict()
        match_date = data.get("matchDate").strftime("%Y-%m-%d")

        while date_idx < len(unique_dates) and unique_dates[date_idx] < match_date:
            for player_id in player_stats:
                avg_score = (
                    player_stats[player_id]["total_score"]
                    / player_stats[player_id]["games"]
                    if player_stats[player_id]["games"] > 0
                    else None
                )
                trend_data["datasets"][player_id]["data"].append(avg_score)
            date_idx += 1

        if data.get("matchType", "singles") == "doubles":
            for ref in data.get("team1", []):
                player_stats[ref.id]["total_score"] += data.get("player1Score", 0)
                player_stats[ref.id]["games"] += 1
            for ref in data.get("team2", []):
                player_stats[ref.id]["total_score"] += data.get("player2Score", 0)
                player_stats[ref.id]["games"] += 1
        else:
            p1_ref, p2_ref = data.get("player1Ref"), data.get("player2Ref")
            if p1_ref:
                player_stats[p1_ref.id]["total_score"] += data.get("player1Score", 0)
                player_stats[p1_ref.id]["games"] += 1
            if p2_ref:
                player_stats[p2_ref.id]["total_score"] += data.get("player2Score", 0)
                player_stats[p2_ref.id]["games"] += 1

        if (
            i == len(matches) - 1
            or matches[i + 1].to_dict().get("matchDate").strftime("%Y-%m-%d")
            != match_date
        ):
            for player_id in player_stats:
                avg_score = (
                    player_stats[player_id]["total_score"]
                    / player_stats[player_id]["games"]
                    if player_stats[player_id]["games"] > 0
                    else None
                )
                trend_data["datasets"][player_id]["data"].append(avg_score)
            date_idx += 1

    for ds in trend_data["datasets"].values():
        while len(ds["data"]) < len(unique_dates):
            ds["data"].append(ds["data"][-1] if ds["data"] else None)

    trend_data["datasets"] = list(trend_data["datasets"].values())
    return trend_data


def get_user_group_stats(db: Client, group_id: str, user_id: str) -> dict[str, Any]:
    """Calculate detailed statistics for a specific user within a group."""
    stats = {
        "rank": "N/A",
        "wins": 0,
        "losses": 0,
        "win_streak": 0,
        "longest_streak": 0,
    }

    leaderboard = get_group_leaderboard(db, group_id)
    for i, player in enumerate(leaderboard):
        if player["id"] == user_id:
            stats["rank"] = i + 1
            stats["wins"] = player.get("wins", 0)
            stats["losses"] = player.get("losses", 0)
            break

    matches_query = db.collection("matches").where(
        filter=FieldFilter("groupId", "==", group_id)
    )
    user_ref = db.collection("users").document(user_id)
    all_matches = list(matches_query.stream())
    all_matches.sort(key=lambda x: x.to_dict().get("matchDate") or datetime.min)

    current_streak = longest_streak = 0

    for match in all_matches:
        data = match.to_dict()
        match_type = data.get("matchType", "singles")
        p1_score = data.get("player1Score", 0)
        p2_score = data.get("player2Score", 0)

        user_is_winner = user_participated = False

        if match_type == "doubles":
            team1 = data.get("team1", [])
            team2 = data.get("team2", [])
            if user_ref in team1:
                user_participated = True
                if p1_score > p2_score:
                    user_is_winner = True
            elif user_ref in team2:
                user_participated = True
                if p2_score > p1_score:
                    user_is_winner = True
        else:
            p1_ref = data.get("player1Ref")
            p2_ref = data.get("player2Ref")
            if user_ref == p1_ref:
                user_participated = True
                if p1_score > p2_score:
                    user_is_winner = True
            elif user_ref == p2_ref:
                user_participated = True
                if p2_score > p1_score:
                    user_is_winner = True

        if user_participated:
            if user_is_winner:
                current_streak += 1
            else:
                longest_streak = max(longest_streak, current_streak)
                current_streak = 0

    longest_streak = max(longest_streak, current_streak)

    stats["longest_streak"] = longest_streak
    stats["win_streak"] = current_streak

    return stats


def send_invite_email_background(
    app, db: Client, invite_token: str, email_data: dict[str, Any]
):
    """Send an invite email in a background thread."""

    def task():
        with app.app_context():
            invite_ref = db.collection("group_invites").document(invite_token)
            try:
                send_email(**email_data)
                invite_ref.update(
                    {"status": "sent", "last_error": firestore.DELETE_FIELD}
                )
            except Exception as e:
                print(f"ERROR: Background invite email failed: {e}", file=sys.stderr)
                invite_ref.update({"status": "failed", "last_error": str(e)})

    thread = threading.Thread(target=task)
    thread.start()


def create_email_invite(
    db: Client,
    group_id: str,
    group_name: str,
    inviter_id: str,
    invitee_name: str,
    invitee_email: str,
) -> dict[str, Any]:
    """Create a group invitation and return the data for sending an email."""
    original_email = invitee_email
    email = original_email.lower()
    users_ref = db.collection("users")
    existing_user = None

    # 1. Check lowercase
    query_lower = users_ref.where(filter=FieldFilter("email", "==", email)).limit(1)
    docs = list(query_lower.stream())

    if docs:
        existing_user = docs[0]
    # 2. Check original if different
    elif original_email != email:
        query_orig = users_ref.where(
            filter=FieldFilter("email", "==", original_email)
        ).limit(1)
        docs = list(query_orig.stream())
        if docs:
            existing_user = docs[0]

    if existing_user:
        # User exists, use their stored email for the invite to ensure
        # matching works
        existing_user.to_dict().get("email")
    else:
        # User does not exist, create a Ghost User This allows matches to
        # be recorded against them before they register
        ghost_user_data = {
            "email": email,
            "name": invitee_name,
            "is_ghost": True,
            "createdAt": firestore.SERVER_TIMESTAMP,
            "username": f"ghost_{secrets.token_hex(4)}",
        }
        db.collection("users").add(ghost_user_data)

    token = secrets.token_urlsafe(32)
    invite_data = {
        "group_id": group_id,
        "email": email,
        "name": invitee_name,
        "inviter_id": inviter_id,
        "created_at": firestore.SERVER_TIMESTAMP,
        "used": False,
        "status": "sending",
    }
    db.collection("group_invites").document(token).set(invite_data)

    return {"token": token, "email": email, "name": invitee_name}


def _get_team_leaderboard(
    db: firestore.Client, member_ids: set[str]
) -> list[dict[str, Any]]:
    """Fetch and calculate the team leaderboard for a group."""
    team_leaderboard = []
    teams_ref = db.collection("teams")
    if not member_ids:
        return []

    member_id_list = list(member_ids)
    team_docs_map = {}

    # Chunk the query to handle Firestore's 30-item limit
    for i in range(0, len(member_id_list), 30):
        chunk = member_id_list[i : i + 30]
        query = teams_ref.where(
            filter=firestore.FieldFilter("member_ids", "array_contains_any", chunk)
        )
        for doc in query.stream():
            team_docs_map[doc.id] = doc

    all_team_docs = list(team_docs_map.values())

    # Filter teams to include only those where all members are in the group
    group_teams = [
        team_doc
        for team_doc in all_team_docs
        if all(
            member_id in member_ids for member_id in team_doc.to_dict()["member_ids"]
        )
    ]

    # Batch fetch all team member details to avoid N+1 queries
    all_member_refs = []
    for team_doc in group_teams:
        team_data = team_doc.to_dict()
        if "members" in team_data:
            all_member_refs.extend(team_data.get("members", []))

    members_map = {}
    if all_member_refs:
        # Deduplicate refs by their path
        unique_member_refs = list({ref.path: ref for ref in all_member_refs}.values())
        member_docs = db.get_all(unique_member_refs)
        members_map = {doc.id: doc.to_dict() for doc in member_docs if doc.exists}

    # Enrich and calculate stats for the leaderboard
    for team_doc in group_teams:
        team_data = team_doc.to_dict()
        team_data["id"] = team_doc.id
        stats = team_data.get("stats", {})
        wins = stats.get("wins", 0)
        losses = stats.get("losses", 0)
        total_games = wins + losses
        team_data["win_percentage"] = (
            (wins / total_games) * 100 if total_games > 0 else 0
        )
        team_data["total_games"] = total_games

        # Get member details from the pre-fetched map
        team_members = []
        member_ids_for_team = team_data.get("member_ids", [])
        for member_id in member_ids_for_team:
            if member_id in members_map:
                member_data = members_map[member_id]
                member_data["id"] = member_id
                team_members.append(member_data)
        team_data["member_details"] = team_members

        # To handle user name changes, we regenerate the default team name.
        if len(team_members) == DOUBLES_TEAM_SIZE:
            member_names = [
                m.get("name") or m.get("username", "Unknown") for m in team_members
            ]
            generated_name = " & ".join(member_names)
            # Simple heuristic to check if the name is default
            if " & " in team_data.get("name", ""):
                team_data["name"] = generated_name

        team_leaderboard.append(team_data)

    # Sort teams by win percentage
    team_leaderboard.sort(key=lambda x: x["win_percentage"], reverse=True)
    return team_leaderboard


def _get_pending_invites(db: firestore.Client, group_id: str) -> list[dict[str, Any]]:
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
        # Chunk the email list to handle Firestore's 30-item limit
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


def _get_recent_matches_and_players(
    db: firestore.Client, group_id: str
) -> tuple[
    list[firestore.DocumentSnapshot],
    dict[str, dict[str, Any]],
    dict[str, dict[str, Any]],
]:
    """Fetch recent matches and a map of all players and teams involved."""
    matches_ref = db.collection("matches")
    matches_query = (
        matches_ref.where(filter=firestore.FieldFilter("groupId", "==", group_id))
        .order_by("matchDate", direction=firestore.Query.DESCENDING)
        .limit(20)
    )
    recent_matches_docs = list(matches_query.stream())

    player_ids = set()
    team_refs = set()
    team_ids = set()
    for match_doc in recent_matches_docs:
        match_data = match_doc.to_dict()
        player_ids.add(
            _get_id(match_data, ["player1", "player1Id", "player1_id", "player_1"])
        )
        player_ids.add(
            _get_id(
                match_data,
                ["player2", "player2Id", "player2_id", "opponent1", "opponent1Id"],
            )
        )
        player_ids.add(_get_id(match_data, ["partnerId", "partner", "partner_id"]))
        player_ids.add(
            _get_id(match_data, ["opponent2Id", "opponent2", "opponent2_id"])
        )
        if match_data.get("team1Ref"):
            team_refs.add(match_data.get("team1Ref"))
        if match_data.get("team2Ref"):
            team_refs.add(match_data.get("team2Ref"))
        if match_data.get("team1Id"):
            team_ids.add(match_data.get("team1Id"))
        if match_data.get("team2Id"):
            team_ids.add(match_data.get("team2Id"))

    player_ids.discard(None)

    users_map = {}
    if player_ids:
        player_id_list = list(player_ids)
        for i in range(0, len(player_id_list), 30):
            chunk = player_id_list[i : i + 30]
            user_docs = (
                db.collection("users")
                .where(filter=firestore.FieldFilter("__name__", "in", chunk))
                .stream()
            )
            for doc in user_docs:
                users_map[doc.id] = doc.to_dict()

    teams_map = {}
    # Combine team IDs from refs and explicit ID fields
    all_team_ids = {ref.id for ref in team_refs} | {
        tid for tid in team_ids if tid
    }
    if all_team_ids:
        all_team_ids_list = list(all_team_ids)
        for i in range(0, len(all_team_ids_list), 30):
            chunk = all_team_ids_list[i : i + 30]
            team_docs = (
                db.collection("teams")
                .where(filter=firestore.FieldFilter("__name__", "in", chunk))
                .stream()
            )
            for doc in team_docs:
                teams_map[doc.id] = doc.to_dict()

    return recent_matches_docs, users_map, teams_map


def _calculate_best_buds(
    db: firestore.Client, group_id: str
) -> Optional[dict[str, Any]]:
    """Calculate the 'best buds' (most successful partnership) in a group."""
    matches_ref = db.collection("matches")
    all_matches_query = matches_ref.where(
        filter=firestore.FieldFilter("groupId", "==", group_id)
    ).select(
        [
            "winner",
            "player1",
            "player1Id",
            "player1_id",
            "player_1",
            "partnerId",
            "partner",
            "partner_id",
            "player2",
            "player2Id",
            "player2_id",
            "opponent1",
            "opponent1Id",
            "opponent2Id",
            "opponent2",
            "opponent2_id",
        ]
    )
    all_matches_docs = list(all_matches_query.stream())
    partnership_wins: dict[tuple[str, str], int] = defaultdict(int)
    for match_doc in all_matches_docs:
        match_data = match_doc.to_dict()

        player1_id = _get_id(
            match_data, ["player1", "player1Id", "player1_id", "player_1"]
        )
        partner_id = _get_id(match_data, ["partnerId", "partner", "partner_id"])
        player2_id = _get_id(
            match_data,
            ["player2", "player2Id", "player2_id", "opponent1", "opponent1Id"],
        )
        opponent2_id = _get_id(match_data, ["opponent2Id", "opponent2", "opponent2_id"])

        is_doubles = all([player1_id, partner_id, player2_id, opponent2_id])

        if is_doubles:
            assert player1_id is not None
            assert partner_id is not None
            assert player2_id is not None
            assert opponent2_id is not None
            winner = match_data.get("winner")
            if winner == "team1":
                winning_pair = tuple(sorted((player1_id, partner_id)))
            elif winner == "team2":
                winning_pair = tuple(sorted((player2_id, opponent2_id)))
            else:
                winning_pair = None

            if winning_pair:
                partnership_wins[winning_pair] += 1

    if not partnership_wins:
        return None

    best_buds_pair = max(partnership_wins, key=partnership_wins.get)

    player1_ref = db.collection("users").document(best_buds_pair[0]).get()
    player2_ref = db.collection("users").document(best_buds_pair[1]).get()

    if player1_ref.exists and player2_ref.exists:
        return {
            "player1": player1_ref.to_dict(),
            "player2": player2_ref.to_dict(),
            "wins": partnership_wins[best_buds_pair],
        }
    return None


def _enrich_matches(
    recent_matches_docs: list[firestore.DocumentSnapshot],
    users_map: dict[str, dict[str, Any]],
    teams_map: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    """Enrich match data with player and team details and check for upsets."""
    recent_matches = []
    for match_doc in recent_matches_docs:
        match_data = match_doc.to_dict()
        match_data["id"] = match_doc.id

        # Handle team-based matches
        team1_ref = match_data.get("team1Ref")
        if team1_ref:
            match_data["team1"] = teams_map.get(team1_ref.id)
        elif match_data.get("team1Id"):
            match_data["team1"] = teams_map.get(match_data.get("team1Id"))

        team2_ref = match_data.get("team2Ref")
        if team2_ref:
            match_data["team2"] = teams_map.get(team2_ref.id)
        elif match_data.get("team2Id"):
            match_data["team2"] = teams_map.get(match_data.get("team2Id"))

        # Handle older, user-based matches as a fallback
        player1_id = _get_id(
            match_data, ["player1", "player1Id", "player1_id", "player_1"]
        )
        if player1_id:
            match_data["player1"] = users_map.get(player1_id, GUEST_USER)
        else:
            match_data["player1"] = GUEST_USER

        player2_id = _get_id(
            match_data,
            ["player2", "player2Id", "player2_id", "opponent1", "opponent1Id"],
        )
        if player2_id:
            match_data["player2"] = users_map.get(player2_id, GUEST_USER)
        else:
            match_data["player2"] = GUEST_USER
        partner_id = _get_id(match_data, ["partnerId", "partner", "partner_id"])
        if partner_id:
            match_data["partner"] = users_map.get(partner_id, GUEST_USER)
        else:
            match_data["partner"] = None

        opponent2_id = _get_id(match_data, ["opponent2Id", "opponent2", "opponent2_id"])
        if opponent2_id:
            match_data["opponent2"] = users_map.get(opponent2_id, GUEST_USER)
        else:
            match_data["opponent2"] = None

        # Giant Slayer Logic
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

        recent_matches.append(match_data)
    return recent_matches


def calculate_head_to_head_stats(
    db: firestore.Client, group_id: str, player1_id: str, player2_id: str
) -> dict[str, Any]:
    """Return head-to-head stats for two players in a group."""
    matches_ref = db.collection("matches")
    query = matches_ref.where(filter=firestore.FieldFilter("groupId", "==", group_id))
    all_matches_in_group = list(query.stream())

    matches = []
    for match_doc in all_matches_in_group:
        match_data = match_doc.to_dict()
        participants = {
            match_data.get("player1Id"),
            match_data.get("player2Id"),
            match_data.get("partnerId"),
            match_data.get("opponent2Id"),
        }
        if player1_id in participants and player2_id in participants:
            matches.append(match_data)

    total_matches = len(matches)
    h2h_player1_wins = 0
    h2h_player2_wins = 0
    partnership_wins = 0
    partnership_losses = 0
    point_differential = 0
    h2h_matches_count = 0
    partnership_matches_count = 0

    for match in matches:
        team1 = {match.get("player1Id"), match.get("partnerId")}
        team2 = {match.get("player2Id"), match.get("opponent2Id")}

        is_partner = (player1_id in team1 and player2_id in team1) or (
            player1_id in team2 and player2_id in team2
        )

        if is_partner:
            partnership_matches_count += 1
            their_team = "team1" if player1_id in team1 else "team2"
            if match.get("winner") == their_team:
                partnership_wins += 1
            else:
                partnership_losses += 1
        else:
            h2h_matches_count += 1
            player1_team = "team1" if player1_id in team1 else "team2"

            if match.get("winner") == player1_team:
                h2h_player1_wins += 1
            else:
                h2h_player2_wins += 1

            team1_score = match.get("team1Score", 0) or 0
            team2_score = match.get("team2Score", 0) or 0
            if player1_team == "team1":
                point_differential += team1_score - team2_score
            else:
                point_differential += team2_score - team1_score

    avg_point_differential = (
        point_differential / h2h_matches_count if h2h_matches_count > 0 else 0
    )

    return {
        "total_matches": total_matches,
        "h2h_matches_count": h2h_matches_count,
        "partnership_matches_count": partnership_matches_count,
        "head_to_head_record": f"{h2h_player1_wins}-{h2h_player2_wins}",
        "partnership_record": f"{partnership_wins}-{partnership_losses}",
        "avg_point_differential": round(avg_point_differential, 1),
    }


def friend_group_members(db, group_id, new_member_ref):
    """Automatically create friend relationships between group members.
    Automatically create friend relationships between the new member and existing
    group members.
    """
    group_ref = db.collection("groups").document(group_id)
    group_doc = group_ref.get()
    if not group_doc.exists:
        return

    group_data = group_doc.to_dict()
    member_refs = group_data.get("members", [])

    if not member_refs:
        return

    batch = db.batch()
    new_member_id = new_member_ref.id
    operation_count = 0

    for member_ref in member_refs:
        if member_ref.id == new_member_id:
            continue

        # Add friend for new member
        new_member_friend_ref = new_member_ref.collection("friends").document(
            member_ref.id
        )
        # Add friend for existing member
        existing_member_friend_ref = member_ref.collection("friends").document(
            new_member_id
        )

        batch.set(
            new_member_friend_ref,
            {"status": "accepted", "initiator": True},
            merge=True,
        )
        batch.set(
            existing_member_friend_ref,
            {"status": "accepted", "initiator": False},
            merge=True,
        )
        operation_count += 2

        # Commit batch if it gets too large (Firestore limit is 500)
        if operation_count >= FIRESTORE_BATCH_LIMIT:
            batch.commit()
            batch = db.batch()
            operation_count = 0

    if operation_count > 0:
        try:
            batch.commit()
        except Exception as e:
            print(f"Error friending group members: {e}", file=sys.stderr)
