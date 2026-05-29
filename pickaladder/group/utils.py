"""Utility functions for the group blueprint."""

from __future__ import annotations

import operator
import secrets
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any

from firebase_admin import firestore

if TYPE_CHECKING:
    from flask import Flask
from google.cloud.firestore import FieldFilter

from pickaladder.core.constants import (
    FIRESTORE_BATCH_LIMIT,
    HOT_STREAK_THRESHOLD,
    JOKES,
    RECENT_MATCHES_LIMIT,
)
from pickaladder.group.services.match_parser import _extract_team_ids, _get_match_scores
from pickaladder.services.mail_service import MailService
from pickaladder.user.helpers import smart_display_name


def get_random_joke() -> str:
    """Return a random sport/dad joke."""
    return secrets.choice(JOKES)


def _initialize_stats(players: list[DocumentSnapshot]) -> dict[str, dict[str, object]]:
    """Initialize the stats dictionary for each player."""
    return {
        ref.id: {
            "wins": 0,
            "losses": 0,
            "games": 0,
            "total_score": 0,
            "user_data": ref.get(),
            "match_results": [],
        }
        for ref in players
    }


def _record_loss(s: dict[str, object], is_draw: bool) -> None:
    """Record a loss if not a draw."""
    if not is_draw:
        s["losses"] += 1


def _update_player_stats(
    stats: dict[str, dict[str, object]],
    player_id: str,
    score: int,
    won: bool,
    is_draw: bool,
) -> None:
    """Update individual player statistics in the stats dictionary."""
    s = stats.get(player_id)
    if not s:
        return
    s["games"] += 1
    s["total_score"] += score
    if won:
        s["wins"] += 1
    else:
        _record_loss(s, is_draw)
    s["match_results"].append("win" if won else "loss")


def _process_single_match(
    stats: dict[str, dict[str, object]], match: DocumentSnapshot
) -> None:
    """Update raw stats and records match outcomes for players in a single match."""
    data = match.to_dict()
    p1_score, p2_score = _get_match_scores(data)

    p1_wins, p2_wins = p1_score > p2_score, p2_score > p1_score
    is_draw = p1_score == p2_score

    team1_ids, team2_ids = _extract_team_ids(data)
    for uid in team1_ids:
        _update_player_stats(stats, uid, p1_score, p1_wins, is_draw)
    for uid in team2_ids:
        _update_player_stats(stats, uid, p2_score, p2_wins, is_draw)


def _calculate_derived_stats(stats: dict[str, dict[str, object]]) -> None:
    """Calculate 'Win Rate %', 'Average Score', and 'Form' (last 5 games)."""
    for s in stats.values():
        games = s["games"]
        s["avg_score"] = s["total_score"] / games if games > 0 else 0.0
        s["win_rate"] = (s["wins"] / games * 100) if games > 0 else 0.0
        s["form"] = s["match_results"][:RECENT_MATCHES_LIMIT]


def _is_ghost(user_data: dict[str, object]) -> bool:
    """Determine if a user is a ghost."""
    return bool(
        user_data.get("is_ghost") or user_data.get("username", "").startswith("ghost_")
    )


def _build_leaderboard_entry(
    user_id: str, user_data: dict[str, object], s: dict[str, object]
) -> dict[str, object]:
    """Build a single leaderboard entry."""
    return {
        "id": user_id,
        "name": smart_display_name(user_data),
        "username": user_data.get("username"),
        "email": user_data.get("email"),
        "profilePictureUrl": user_data.get("profilePictureUrl"),
        "profilePictureThumbnailUrl": user_data.get("profilePictureThumbnailUrl"),
        "is_ghost": _is_ghost(user_data),
        "wins": s["wins"],
        "losses": s["losses"],
        "games_played": s["games"],
        "avg_score": s["avg_score"],
        "win_rate": s["win_rate"],
        "form": s["form"],
    }


def _sort_leaderboard(stats: dict[str, dict[str, object]]) -> list[dict[str, object]]:
    """Enrich stats with user data, format into a list, and sort."""
    leaderboard = []
    for user_id, s in stats.items():
        user_doc = s["user_data"]
        if not user_doc.exists or user_doc.to_dict() is None:
            continue
        user_data = user_doc.to_dict()
        user_data["id"] = user_id
        leaderboard.append(_build_leaderboard_entry(user_id, user_data, s))

    leaderboard.sort(
        key=operator.itemgetter("avg_score", "wins", "games_played"), reverse=True
    )
    return leaderboard


def _calculate_leaderboard_from_matches(
    matches: list[DocumentSnapshot], players: list[DocumentSnapshot]
) -> list[dict[str, object]]:
    """Calculate the leaderboard from a list of matches using a pipeline of helpers."""
    matches.sort(
        key=lambda m: m.to_dict().get("matchDate") or datetime.min, reverse=True
    )

    stats = _initialize_stats(players)
    for match in matches:
        _process_single_match(stats, match)

    _calculate_derived_stats(stats)
    return _sort_leaderboard(stats)


def _calculate_rank_changes(
    current_leaderboard: list[dict[str, object]],
    previous_leaderboard: list[dict[str, object]],
) -> None:
    """Calculate rank changes between current and previous leaderboard."""
    last_week_ranks = {
        player["id"]: i + 1 for i, player in enumerate(previous_leaderboard)
    }

    for i, player in enumerate(current_leaderboard):
        current_rank = i + 1
        last_week_rank = last_week_ranks.get(player["id"])
        if last_week_rank is not None:
            player["rank_change"] = last_week_rank - current_rank
        else:
            player["rank_change"] = "new"


def _add_match_to_user_map(
    user_matches_map: dict[str, list[dict[str, object]]], data: dict[str, object]
) -> None:
    """Helper to add a match to all involved users in the map."""
    team1_ids, team2_ids = _extract_team_ids(data)
    for uid in team1_ids.union(team2_ids):
        if uid in user_matches_map:
            user_matches_map[uid].append(data)


def _map_matches_to_users(
    matches: list[DocumentSnapshot], member_refs: list[DocumentSnapshot]
) -> dict[str, list[dict[str, object]]]:
    """Map matches to each user for efficient lookup."""
    user_matches_map: dict[str, list[dict[str, object]]] = {
        ref.id: [] for ref in member_refs
    }
    for match in matches:
        _add_match_to_user_map(user_matches_map, match.to_dict())
    return user_matches_map


def _is_match_won(user_id: str, data: dict[str, object]) -> bool:
    """Determine if a player won a specific match."""
    p1_score, p2_score = _get_match_scores(data)
    team1_ids, team2_ids = _extract_team_ids(data)
    if user_id in team1_ids:
        return p1_score > p2_score
    if user_id in team2_ids:
        return p2_score > p1_score
    return False


def _update_streak(streak: int, user_id: str, data: dict[str, object]) -> int:
    """Update streak count for a single match."""
    p1_score, p2_score = _get_match_scores(data)
    if p1_score == p2_score or not _is_match_won(user_id, data):
        return -1  # Indicates streak broken
    return streak + 1


def _calculate_player_winning_streak(
    user_id: str, matches_data: list[dict[str, object]]
) -> int:
    """Calculate the current winning streak for a single player."""
    streak = 0
    for data in matches_data:
        res = _update_streak(streak, user_id, data)
        if res == -1:
            break
        streak = res
    return streak


def _calculate_winning_streaks(
    leaderboard: list[dict[str, object]],
    matches: list[DocumentSnapshot],
    member_refs: list[DocumentSnapshot],
) -> None:
    """Calculate winning streaks for players in the leaderboard."""
    user_matches_map = _map_matches_to_users(matches, member_refs)

    for player in leaderboard:
        user_id = player["id"]
        matches_data = user_matches_map.get(user_id, [])
        player["streak"] = _calculate_player_winning_streak(user_id, matches_data)
        player["is_on_fire"] = player["streak"] >= HOT_STREAK_THRESHOLD


def get_group_leaderboard(group_id: str) -> list[dict[str, object]]:
    """Calculate the leaderboard for a specific group using Firestore."""
    db = firestore.client()
    group_ref = db.collection("groups").document(group_id)
    group = group_ref.get()
    if not group.exists:
        return []

    group_data = group.to_dict()
    member_refs = group_data.get("members", [])
    if not member_refs:
        return []

    stream = (
        db.collection("matches")
        .where(filter=FieldFilter("groupId", "==", group_id))
        .stream()
    )
    all_matches = list(stream)
    current_leaderboard = _calculate_leaderboard_from_matches(all_matches, member_refs)

    one_week_ago = datetime.now(timezone.utc) - timedelta(days=7)
    matches_last_week = [
        m
        for m in all_matches
        if m.to_dict().get("matchDate") and m.to_dict().get("matchDate") < one_week_ago
    ]
    last_week_leaderboard = _calculate_leaderboard_from_matches(
        matches_last_week, member_refs
    )

    _calculate_rank_changes(current_leaderboard, last_week_leaderboard)
    all_matches.sort(
        key=lambda m: m.to_dict().get("matchDate") or datetime.min, reverse=True
    )
    _calculate_winning_streaks(current_leaderboard, all_matches, member_refs)

    return current_leaderboard


def _collect_match_player_refs(data: dict[str, object], all_player_refs: set) -> None:
    """Collect player references from a single match data dictionary."""
    if data.get("matchType", "singles") == "doubles":
        all_player_refs.update(data.get("team1", []))
        all_player_refs.update(data.get("team2", []))
    else:
        refs = [data.get("player1Ref"), data.get("player2Ref")]
        all_player_refs.update({r for r in refs if r})


def _extract_basic_player_data(doc: DocumentSnapshot) -> dict[str, object]:
    """Extract name and profile picture URL from a player document."""
    data = doc.to_dict()
    return {
        "name": data.get("name", "Unknown"),
        "profilePictureUrl": data.get("profilePictureUrl"),
    }


def _get_involved_player_data(
    db: Client, matches: list[DocumentSnapshot]
) -> dict[str, dict[str, object]]:
    """Get profile data for all players involved in matches."""
    all_player_refs: set[DocumentReference] = set()
    for match in matches:
        _collect_match_player_refs(match.to_dict(), all_player_refs)

    player_docs = db.get_all(list(all_player_refs))
    return {
        doc.id: _extract_basic_player_data(doc) for doc in player_docs if doc.exists
    }


def _record_trend_averages(
    player_stats: dict[str, object], datasets: dict[str, object]
) -> None:
    """Calculate and record current average scores for all players in trend datasets."""
    for pid, stats in player_stats.items():
        avg = stats["total_score"] / stats["games"] if stats["games"] > 0 else None
        datasets[pid]["data"].append(avg)


def _process_trend_date_change(
    unique_dates: list[str],
    date_idx: int,
    match_date: str,
    player_stats: dict[str, object],
    datasets: dict[str, object],
) -> int:
    """Process date advancement in trend points calculation."""
    while date_idx < len(unique_dates) and unique_dates[date_idx] < match_date:
        _record_trend_averages(player_stats, datasets)
        date_idx += 1
    return date_idx


def _calculate_trend_points(
    matches: list[DocumentSnapshot],
    players_data: dict[str, object],
    unique_dates: list[str],
) -> dict[str, dict[str, object]]:
    """Calculate average score trend points for each player."""
    player_stats = {pid: {"total_score": 0, "games": 0} for pid in players_data}
    datasets = {
        pid: {
            "id": pid,
            "label": info["name"],
            "data": [],
            "fill": False,
            "profilePictureUrl": info["profilePictureUrl"],
        }
        for pid, info in players_data.items()
    }

    date_idx = 0
    for i, match in enumerate(matches):
        data = match.to_dict()
        match_date = data.get("matchDate").strftime("%Y-%m-%d")
        date_idx = _process_trend_date_change(
            unique_dates, date_idx, match_date, player_stats, datasets
        )
        _update_trend_player_stats(player_stats, data)

        is_last = i == len(matches) - 1
        if (
            is_last
            or matches[i + 1].to_dict().get("matchDate").strftime("%Y-%m-%d")
            != match_date
        ):
            _record_trend_averages(player_stats, datasets)
            date_idx += 1

    return datasets


def _update_player_trend_stats(
    player_stats: dict[str, object], uid: str, score: int
) -> None:
    """Update running totals for a single player in trend calculation."""
    if uid in player_stats:
        player_stats[uid]["total_score"] += score
        player_stats[uid]["games"] += 1


def _update_trend_player_stats(
    player_stats: dict[str, object], match_data: dict[str, object]
) -> None:
    """Update running totals for trend calculation from a single match."""
    p1_score, p2_score = _get_match_scores(match_data)
    team1_ids, team2_ids = _extract_team_ids(match_data)

    for uid in team1_ids:
        _update_player_trend_stats(player_stats, uid, p1_score)
    for uid in team2_ids:
        _update_player_trend_stats(player_stats, uid, p2_score)


def _pad_trend_datasets(
    datasets_dict: dict[str, object], unique_dates: list[str]
) -> None:
    """Pad trend datasets with last value until current date."""
    for ds in datasets_dict.values():
        while len(ds["data"]) < len(unique_dates):
            ds["data"].append(ds["data"][-1] if ds["data"] else None)


def get_leaderboard_trend_data(group_id: str) -> dict[str, object]:
    """Generate data for a leaderboard trend chart."""
    db = firestore.client()
    query = db.collection("matches").where(
        filter=FieldFilter("groupId", "==", group_id)
    )
    matches = [m for m in query.stream() if m.to_dict().get("matchDate")]
    matches.sort(key=lambda x: x.to_dict().get("matchDate"))
    if not matches:
        return {"labels": [], "datasets": []}

    players_data = _get_involved_player_data(db, matches)
    unique_dates = sorted(
        list({m.to_dict().get("matchDate").strftime("%Y-%m-%d") for m in matches})
    )
    datasets_dict = _calculate_trend_points(matches, players_data, unique_dates)
    _pad_trend_datasets(datasets_dict, unique_dates)

    return {"labels": unique_dates, "datasets": list(datasets_dict.values())}


def _check_partnership_win(
    data: dict[str, object], playerA_id: str, playerB_id: str, wins: int, losses: int
) -> tuple[int, int]:
    """Determine if a partnership won or lost a specific match."""
    team1_ids, team2_ids = _extract_team_ids(data)
    p1_score, p2_score = _get_match_scores(data)
    partners = {playerA_id, playerB_id}

    if partners.issubset(team1_ids):
        wins += 1 if p1_score > p2_score else 0
        losses += 1 if p2_score > p1_score else 0
    elif partners.issubset(team2_ids):
        wins += 1 if p2_score > p1_score else 0
        losses += 1 if p1_score > p2_score else 0
    return wins, losses


def get_partnership_stats(
    playerA_id: str, playerB_id: str, all_matches_in_group: list[DocumentSnapshot]
) -> dict[str, int]:
    """Calculates the win/loss record for two players when they are partners."""
    wins = losses = 0

    for match_doc in all_matches_in_group:
        data = match_doc.to_dict()
        if data.get("matchType") == "doubles":
            wins, losses = _check_partnership_win(
                data, playerA_id, playerB_id, wins, losses
            )

    return {"wins": wins, "losses": losses}


def _update_h2h_win_loss(stats: dict[str, object], won: bool, lost: bool) -> None:
    """Update win/loss counts for head-to-head stats."""
    if won:
        stats["wins"] += 1
    elif lost:
        stats["losses"] += 1


def _update_h2h_stats(
    stats: dict[str, object], p1_score: int, p2_score: int, player_a_is_t1: bool
) -> None:
    """Update the running head-to-head statistics."""
    if player_a_is_t1:
        diff, a_pts, b_pts = p1_score - p2_score, p1_score, p2_score
        won, lost = p1_score > p2_score, p2_score > p1_score
    else:
        diff, a_pts, b_pts = p2_score - p1_score, p2_score, p1_score
        won, lost = p2_score > p1_score, p1_score > p2_score

    stats["point_diff"] += diff
    stats["playerA_total_points"] += a_pts
    stats["playerB_total_points"] += b_pts
    _update_h2h_win_loss(stats, won, lost)


def _process_h2h_match(
    match_doc: DocumentSnapshot,
    playerA_id: str,
    playerB_id: str,
    stats: dict[str, object],
) -> None:
    """Process a single match for head-to-head statistics."""
    data = match_doc.to_dict()
    team1_ids, team2_ids = _extract_team_ids(data)

    player_a_is_t1 = playerA_id in team1_ids
    player_b_is_t2 = playerB_id in team2_ids
    player_a_is_t2 = playerA_id in team2_ids
    player_b_is_t1 = playerB_id in team1_ids

    if not ((player_a_is_t1 and player_b_is_t2) or (player_a_is_t2 and player_b_is_t1)):
        return

    match_display_data = data.copy()
    match_display_data["id"] = match_doc.id
    match_display_data["team1_ids"] = list(team1_ids)
    match_display_data["team2_ids"] = list(team2_ids)
    stats["matches"].append(match_display_data)

    p1_score, p2_score = _get_match_scores(data)
    _update_h2h_stats(stats, p1_score, p2_score, player_a_is_t1)


def get_head_to_head_stats(
    group_id: str, playerA_id: str, playerB_id: str
) -> dict[str, object]:
    """Calculates head-to-head statistics for two players in doubles matches."""
    db = firestore.client()
    query = db.collection("matches").where(
        filter=FieldFilter("groupId", "==", group_id)
    )
    all_matches_in_group = list(query.stream())

    h2h_stats: dict[str, object] = {
        "wins": 0,
        "losses": 0,
        "point_diff": 0,
        "playerA_total_points": 0,
        "playerB_total_points": 0,
        "matches": [],
    }

    for match_doc in all_matches_in_group:
        _process_h2h_match(match_doc, playerA_id, playerB_id, h2h_stats)

    num_matches = len(h2h_stats["matches"])
    avg_A = h2h_stats["playerA_total_points"] / num_matches if num_matches > 0 else 0
    avg_B = h2h_stats["playerB_total_points"] / num_matches if num_matches > 0 else 0

    return {
        "wins": h2h_stats["wins"],
        "losses": h2h_stats["losses"],
        "matches": h2h_stats["matches"],
        "point_diff": h2h_stats["point_diff"],
        "avg_points_scored": {"playerA": avg_A, "playerB": avg_B},
        "partnership_record": get_partnership_stats(
            playerA_id, playerB_id, all_matches_in_group
        ),
    }


def _get_user_win(
    user_id: str, team1_ids: set, team2_ids: set, p1_score: int, p2_score: int
) -> bool | None:
    """Determine if a user won, lost, or didn't participate."""
    if user_id in team1_ids:
        return p1_score > p2_score
    if user_id in team2_ids:
        return p2_score > p1_score
    return None


def _update_all_time_streak(
    data: dict[str, object], user_id: str, current: int, longest: int
) -> tuple[int, int]:
    """Update current and longest winning streaks based on a single match."""
    p1_score, p2_score = _get_match_scores(data)
    team1_ids, team2_ids = _extract_team_ids(data)

    user_won = _get_user_win(user_id, team1_ids, team2_ids, p1_score, p2_score)
    if user_won is None:
        return current, longest

    if user_won:
        current += 1
    else:
        longest, current = max(longest, current), 0
    return current, longest


def _calculate_all_time_streaks(
    matches: list[DocumentSnapshot], user_ref: DocumentReference
) -> tuple[int, int]:
    """Calculate current and longest winning streaks for a user."""
    matches.sort(key=lambda x: x.to_dict().get("matchDate") or datetime.min)
    current = longest = 0

    for match in matches:
        current, longest = _update_all_time_streak(
            match.to_dict(), user_ref.id, current, longest
        )

    return current, max(longest, current)


def get_user_group_stats(group_id: str, user_id: str) -> dict[str, object]:
    """Calculate detailed statistics for a specific user within a group."""
    leaderboard = get_group_leaderboard(group_id)
    user_data = next((p for p in leaderboard if p["id"] == user_id), None)

    stats = {
        "rank": "N/A",
        "wins": 0,
        "losses": 0,
        "win_streak": 0,
        "longest_streak": 0,
    }

    if user_data:
        stats["rank"] = leaderboard.index(user_data) + 1
        stats["wins"], stats["losses"] = (
            user_data.get("wins", 0),
            user_data.get("losses", 0),
        )

    db = firestore.client()
    query = db.collection("matches").where(
        filter=FieldFilter("groupId", "==", group_id)
    )
    all_matches = list(query.stream())

    curr, long = _calculate_all_time_streaks(
        all_matches, db.collection("users").document(user_id)
    )
    stats["win_streak"], stats["longest_streak"] = curr, long

    return stats


def _perform_invite_email_task(invite_token: str, email_data: dict[str, Any]) -> None:
    """Perform the email sending task synchronously (meant for background thread)."""
    db = firestore.client()
    invite_ref = db.collection("group_invites").document(invite_token)
    try:
        MailService.send_email_now(**email_data)
        invite_ref.update({"status": "sent", "last_error": firestore.DELETE_FIELD})
    except Exception as e:
        invite_ref.update({"status": "failed", "last_error": str(e)})
        raise


def send_invite_email_background(
    app: Flask, invite_token: str, email_data: dict[str, Any]
) -> None:
    """Send an invite email using the centralized TaskExecutor."""
    from pickaladder.extensions import executor

    executor.run_async(_perform_invite_email_task, invite_token, email_data)


def _add_friend_pair(
    batch: WriteBatch, member_ref: DocumentReference, new_member_ref: DocumentReference
) -> int:
    """Add a bidirectional friendship between two members in a Firestore batch."""
    new_member_friend_ref = new_member_ref.collection("friends").document(member_ref.id)
    existing_member_friend_ref = member_ref.collection("friends").document(
        new_member_ref.id
    )

    batch.set(
        new_member_friend_ref, {"status": "accepted", "initiator": True}, merge=True
    )
    batch.set(
        existing_member_friend_ref,
        {"status": "accepted", "initiator": False},
        merge=True,
    )
    return 2


def _get_group_member_refs(db: Client, group_id: str) -> list[DocumentSnapshot]:
    """Retrieve member references for a group."""
    group_ref = db.collection("groups").document(group_id)
    group_doc = group_ref.get()
    if not group_doc.exists:
        return []
    return group_doc.to_dict().get("members", [])


def _commit_batch(db: Client, batch: WriteBatch) -> Response | str | dict[str, object]:
    """Commit current batch and return a new one."""
    batch.commit()
    return db.batch()


def _process_friend_ref(
    batch: WriteBatch, member_ref: DocumentReference, new_member_ref: DocumentReference
) -> int:
    """Helper to process a single friend ref and return number of operations."""
    if member_ref.id == new_member_ref.id:
        return 0
    return _add_friend_pair(batch, member_ref, new_member_ref)


def _batch_step(
    db: Client,
    batch: WriteBatch,
    count: int,
    ref: DocumentReference,
    new_ref: DocumentReference,
) -> tuple[WriteBatch, int]:
    """Single step in friendship batch processing."""
    count += _process_friend_ref(batch, ref, new_ref)
    if count >= FIRESTORE_BATCH_LIMIT:
        return _commit_batch(db, batch), 0
    return batch, count


def _process_friendship_batch(
    db: Client, member_refs: list[DocumentSnapshot], new_member_ref: DocumentReference
) -> None:
    """Process friendship additions in batches."""
    batch, count = db.batch(), 0
    for ref in member_refs:
        batch, count = _batch_step(db, batch, count, ref, new_member_ref)
    if count > 0:
        batch.commit()


def friend_group_members(
    db: Client, group_id: str, new_member_ref: DocumentReference
) -> None:
    """Automatically create friend relationships between group members."""
    member_refs = _get_group_member_refs(db, group_id)
    if member_refs:
        _process_friendship_batch(db, member_refs, new_member_ref)
