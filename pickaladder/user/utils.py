"""Utility functions for user management."""

from __future__ import annotations

import datetime
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple, Union, cast

from firebase_admin import firestore
from flask import current_app

if TYPE_CHECKING:
    from google.cloud.firestore_v1.base_document import DocumentSnapshot
    from google.cloud.firestore_v1.client import Client

from pickaladder.utils import mask_email

from .models import User


def merge_ghost_user(db: Client, real_user_ref: Any, email: str) -> None:
    """Check for 'ghost' user with the given email and merge their data.

    This function should be called when a user registers or logs in for the first
    time to ensure any matches recorded against their invitation (ghost profile)
    are transferred.
    """
    try:
        users_ref = db.collection("users")
        # Find ghost user by email (lowercase)
        # Note: Ghost users are always created with lowercase email
        query = (
            users_ref.where(filter=firestore.FieldFilter("email", "==", email.lower()))
            .where(filter=firestore.FieldFilter("is_ghost", "==", True))
            .limit(1)
        )

        ghost_docs = list(query.stream())
        if not ghost_docs:
            return

        ghost_doc = ghost_docs[0]
        ghost_ref = ghost_doc.reference

        current_app.logger.info(
            f"Merging ghost user {ghost_doc.id} to real user {real_user_ref.id}"
        )

        batch = db.batch()

        # 1. Update Matches where ghost is player1Ref
        matches_p1 = (
            db.collection("matches")
            .where(filter=firestore.FieldFilter("player1Ref", "==", ghost_ref))
            .stream()
        )
        for match in matches_p1:
            batch.update(match.reference, {"player1Ref": real_user_ref})

        # 2. Update Matches where ghost is player2Ref
        matches_p2 = (
            db.collection("matches")
            .where(filter=firestore.FieldFilter("player2Ref", "==", ghost_ref))
            .stream()
        )
        for match in matches_p2:
            batch.update(match.reference, {"player2Ref": real_user_ref})

        # 3. Update Matches where ghost is in team1
        matches_t1 = (
            db.collection("matches")
            .where(filter=firestore.FieldFilter("team1", "array_contains", ghost_ref))
            .stream()
        )
        for match in matches_t1:
            batch.update(match.reference, {"team1": firestore.ArrayRemove([ghost_ref])})
            batch.update(
                match.reference, {"team1": firestore.ArrayUnion([real_user_ref])}
            )

        # 4. Update Matches where ghost is in team2
        matches_t2 = (
            db.collection("matches")
            .where(filter=firestore.FieldFilter("team2", "array_contains", ghost_ref))
            .stream()
        )
        for match in matches_t2:
            batch.update(match.reference, {"team2": firestore.ArrayRemove([ghost_ref])})
            batch.update(
                match.reference, {"team2": firestore.ArrayUnion([real_user_ref])}
            )

        # 5. Update Groups where ghost is a member
        groups_member = (
            db.collection("groups")
            .where(filter=firestore.FieldFilter("members", "array_contains", ghost_ref))
            .stream()
        )
        for group in groups_member:
            batch.update(
                group.reference, {"members": firestore.ArrayRemove([ghost_ref])}
            )
            batch.update(
                group.reference, {"members": firestore.ArrayUnion([real_user_ref])}
            )

        # 6. Delete the ghost user document
        batch.delete(ghost_ref)

        batch.commit()
        current_app.logger.info("Ghost user merge completed successfully.")

    except Exception as e:
        current_app.logger.error(f"Error merging ghost user: {e}")


def wrap_user(
    user_data: Optional[Dict[str, Any]], uid: Optional[str] = None
) -> Optional[User]:
    """Wrap a user dictionary in a User model object.

    Args:
        user_data: The user data dictionary from Firestore.
        uid: Optional user ID if not present in user_data.

    Returns:
        A User model object or None if user_data is None.
    """
    if user_data is None:
        return None
    if isinstance(user_data, User):
        return user_data

    data = dict(user_data)
    if uid:
        data["uid"] = uid
    return User(data)


def smart_display_name(user: Dict[str, Any]) -> str:
    """Return a smart display name for a user.

    If the user is a ghost user (username starts with 'ghost_'):
    - If they have an email, return a masked version of it.
    - If they have no name, return 'Pending Invite'.
    Otherwise, return the username.
    """
    username = user.get("username", "")
    if username.startswith("ghost_"):
        email = user.get("email")
        if email:
            return mask_email(email)
        if not user.get("name"):
            return "Pending Invite"

    return username


class UserService:
    """Service class for user-related operations."""

    @staticmethod
    def get_user_by_id(db: Client, user_id: str) -> Optional[Dict[str, Any]]:
        """Fetch a user by their ID."""
        user_ref = db.collection("users").document(user_id)
        user_doc = cast("DocumentSnapshot", user_ref.get())
        if not user_doc.exists:
            return None
        data = user_doc.to_dict()
        if data is None:
            return None
        data["id"] = user_id
        return data

    @staticmethod
    def get_friendship_info(
        db: Client, current_user_id: str, target_user_id: str
    ) -> Tuple[bool, bool]:
        """Check friendship status between two users."""
        friend_request_sent = is_friend = False
        if current_user_id != target_user_id:
            friend_ref = (
                db.collection("users")
                .document(current_user_id)
                .collection("friends")
                .document(target_user_id)
            )
            friend_doc = friend_ref.get()
            if friend_doc.exists:
                status = friend_doc.to_dict().get("status")
                if status == "accepted":
                    is_friend = True
                elif status == "pending":
                    friend_request_sent = True
        return is_friend, friend_request_sent

    @staticmethod
    def get_user_friends(
        db: Client, user_id: str, limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Fetch a user's friends."""
        user_ref = db.collection("users").document(user_id)
        query = user_ref.collection("friends").where(
            filter=firestore.FieldFilter("status", "==", "accepted")
        )
        if limit:
            query = query.limit(limit)

        friends_query = query.stream()
        friend_ids = [f.id for f in friends_query]
        if not friend_ids:
            return []

        refs = [db.collection("users").document(fid) for fid in friend_ids]
        friend_docs = cast(List["DocumentSnapshot"], db.get_all(refs))
        results = []
        for doc in friend_docs:
            if doc.exists:
                data = doc.to_dict()
                if data is not None:
                    results.append({"id": doc.id, **data})
        return results

    @staticmethod
    def get_user_pending_requests(db: Client, user_id: str) -> List[Dict[str, Any]]:
        """Fetch pending friend requests where the user is the recipient."""
        user_ref = db.collection("users").document(user_id)
        requests_query = (
            user_ref.collection("friends")
            .where(filter=firestore.FieldFilter("status", "==", "pending"))
            .where(filter=firestore.FieldFilter("initiator", "==", False))
            .stream()
        )
        request_ids = [doc.id for doc in requests_query]
        if not request_ids:
            return []

        refs = [db.collection("users").document(uid) for uid in request_ids]
        request_docs = cast(List["DocumentSnapshot"], db.get_all(refs))
        results = []
        for doc in request_docs:
            if doc.exists:
                data = doc.to_dict()
                if data is not None:
                    results.append({"id": doc.id, **data})
        return results

    @staticmethod
    def get_user_sent_requests(db: Client, user_id: str) -> List[Dict[str, Any]]:
        """Fetch pending friend requests where the user is the initiator."""
        user_ref = db.collection("users").document(user_id)
        requests_query = (
            user_ref.collection("friends")
            .where(filter=firestore.FieldFilter("status", "==", "pending"))
            .where(filter=firestore.FieldFilter("initiator", "==", True))
            .stream()
        )
        request_ids = [doc.id for doc in requests_query]
        if not request_ids:
            return []

        refs = [db.collection("users").document(uid) for uid in request_ids]
        request_docs = cast(List["DocumentSnapshot"], db.get_all(refs))
        results = []
        for doc in request_docs:
            if doc.exists:
                data = doc.to_dict()
                if data is not None:
                    results.append({"id": doc.id, **data})
        return results

    @staticmethod
    def get_all_users(
        db: Client, exclude_user_id: str, limit: int = 20
    ) -> List[Dict[str, Any]]:
        """Fetch a list of users, excluding the current user, sorted by date."""
        users_query = (
            db.collection("users")
            .order_by("createdAt", direction=firestore.Query.DESCENDING)
            .limit(limit + 1)  # Fetch one extra in case we exclude the current user
            .stream()
        )
        users = []
        for doc in users_query:
            if doc.id == exclude_user_id:
                continue
            data = doc.to_dict()
            if data is not None:
                data["id"] = doc.id
                users.append(data)
            if len(users) >= limit:
                break
        return users

    @staticmethod
    def get_h2h_stats(
        db: Client, user_id_1: str, user_id_2: str
    ) -> Optional[Dict[str, Any]]:
        """Fetch head-to-head statistics between two users."""
        my_wins = 0
        my_losses = 0
        point_diff = 0

        # Singles matches
        singles_query_1 = (
            db.collection("matches")
            .where(filter=firestore.FieldFilter("player1Id", "==", user_id_1))
            .where(filter=firestore.FieldFilter("player2Id", "==", user_id_2))
            .where(filter=firestore.FieldFilter("status", "==", "completed"))
            .stream()
        )
        singles_query_2 = (
            db.collection("matches")
            .where(filter=firestore.FieldFilter("player1Id", "==", user_id_2))
            .where(filter=firestore.FieldFilter("player2Id", "==", user_id_1))
            .where(filter=firestore.FieldFilter("status", "==", "completed"))
            .stream()
        )

        for match in singles_query_1:
            data = match.to_dict()
            if data is None:
                continue
            if data.get("winnerId") == user_id_1:
                my_wins += 1
            else:
                my_losses += 1
            point_diff += data.get("player1Score", 0) - data.get("player2Score", 0)

        for match in singles_query_2:
            data = match.to_dict()
            if data is None:
                continue
            if data.get("winnerId") == user_id_1:
                my_wins += 1
            else:
                my_losses += 1
            point_diff += data.get("player2Score", 0) - data.get("player1Score", 0)

        # Doubles matches
        doubles_query = (
            db.collection("matches")
            .where(
                filter=firestore.FieldFilter(
                    "participants", "array_contains", user_id_1
                )
            )
            .where(filter=firestore.FieldFilter("matchType", "==", "doubles"))
            .where(filter=firestore.FieldFilter("status", "==", "completed"))
            .stream()
        )

        for match in doubles_query:
            data = match.to_dict()
            if data is None:
                continue
            participants = data.get("participants", [])
            if user_id_2 in participants:
                team1_ids = data.get("team1Id", [])
                team2_ids = data.get("team2Id", [])

                user_in_team1 = user_id_1 in team1_ids
                opponent_in_team2 = user_id_2 in team2_ids
                user_in_team2 = user_id_1 in team2_ids
                opponent_in_team1 = user_id_2 in team1_ids

                if user_in_team1 and opponent_in_team2:
                    if data.get("winnerId") == "team1":
                        my_wins += 1
                    else:
                        my_losses += 1
                    point_diff += data.get("player1Score", 0) - data.get(
                        "player2Score", 0
                    )
                elif user_in_team2 and opponent_in_team1:
                    if data.get("winnerId") == "team2":
                        my_wins += 1
                    else:
                        my_losses += 1
                    point_diff += data.get("player2Score", 0) - data.get(
                        "player1Score", 0
                    )

        if my_wins > 0 or my_losses > 0:
            return {
                "wins": my_wins,
                "losses": my_losses,
                "point_diff": point_diff,
            }
        return None

    @staticmethod
    def get_user_matches(db: Client, user_id: str) -> List[Any]:
        """Fetch all matches involving a user."""
        user_ref = db.collection("users").document(user_id)
        matches_as_p1 = (
            db.collection("matches")
            .where(filter=firestore.FieldFilter("player1Ref", "==", user_ref))
            .stream()
        )
        matches_as_p2 = (
            db.collection("matches")
            .where(filter=firestore.FieldFilter("player2Ref", "==", user_ref))
            .stream()
        )
        matches_as_t1 = (
            db.collection("matches")
            .where(filter=firestore.FieldFilter("team1", "array_contains", user_ref))
            .stream()
        )
        matches_as_t2 = (
            db.collection("matches")
            .where(filter=firestore.FieldFilter("team2", "array_contains", user_ref))
            .stream()
        )

        all_matches = (
            list(matches_as_p1)
            + list(matches_as_p2)
            + list(matches_as_t1)
            + list(matches_as_t2)
        )
        unique_matches = {match.id: match for match in all_matches}.values()
        return list(unique_matches)

    @staticmethod
    def calculate_stats(matches: List[Any], user_id: str) -> Dict[str, Any]:
        """Calculate statistics (wins, losses, streak) from matches."""
        wins = 0
        losses = 0
        all_processed_matches = []

        for match_doc in matches:
            match_data = match_doc.to_dict()
            if match_data is None:
                continue
            match_type = match_data.get("matchType", "singles")
            p1_score = match_data.get("player1Score", 0)
            p2_score = match_data.get("player2Score", 0)

            user_won = False
            user_lost = False

            if match_type == "doubles":
                team1_refs = match_data.get("team1", [])
                in_team1 = any(ref.id == user_id for ref in team1_refs)

                if in_team1:
                    if p1_score > p2_score:
                        user_won = True
                    else:
                        user_lost = True
                elif p2_score > p1_score:
                    user_won = True
                else:
                    user_lost = True
            else:
                p1_ref = match_data.get("player1Ref")
                is_player1 = p1_ref and p1_ref.id == user_id
                if is_player1:
                    if p1_score > p2_score:
                        user_won = True
                    else:
                        user_lost = True
                elif p2_score > p1_score:
                    user_won = True
                else:
                    user_lost = True

            if user_won:
                wins += 1
            elif user_lost:
                losses += 1

            all_processed_matches.append(
                {
                    "doc": match_doc,
                    "data": match_data,
                    "date": match_data.get("matchDate") or match_doc.create_time,
                    "user_won": user_won,
                }
            )

        total_games = wins + losses
        win_rate = (wins / total_games) * 100 if total_games > 0 else 0

        # Sort matches for streak calculation
        all_processed_matches.sort(
            key=lambda x: x["date"] or datetime.datetime.min, reverse=True
        )

        current_streak = 0
        streak_type = "N/A"
        if all_processed_matches:
            last_result = all_processed_matches[0]["user_won"]
            streak_type = "W" if last_result else "L"
            for match in all_processed_matches:
                if match["user_won"] == last_result:
                    current_streak += 1
                else:
                    break

        return {
            "wins": wins,
            "losses": losses,
            "total_games": total_games,
            "win_rate": win_rate,
            "current_streak": current_streak,
            "streak_type": streak_type,
            "processed_matches": all_processed_matches,
        }

    @staticmethod
    def get_group_rankings(db: Client, user_id: str) -> List[Dict[str, Any]]:
        """Fetch group rankings for a user."""
        from pickaladder.group.utils import get_group_leaderboard  # noqa: PLC0415

        user_ref = db.collection("users").document(user_id)
        group_rankings = []
        my_groups_query = (
            db.collection("groups")
            .where(filter=firestore.FieldFilter("members", "array_contains", user_ref))
            .stream()
        )
        for group_doc in my_groups_query:
            group_data = group_doc.to_dict()
            if group_data is None:
                continue
            leaderboard = get_group_leaderboard(group_doc.id)
            user_ranking_data = None
            for i, player in enumerate(leaderboard):
                if player["id"] == user_id:
                    rank = i + 1
                    user_ranking_data = {
                        "group_id": group_doc.id,
                        "group_name": group_data.get("name", "N/A"),
                        "rank": rank,
                        "points": player.get("avg_score", 0),
                        "form": player.get("form", []),
                    }
                    if i > 0:
                        player_above = leaderboard[i - 1]
                        user_ranking_data["player_above"] = player_above.get("name")
                        user_ranking_data["points_to_overtake"] = player_above.get(
                            "avg_score", 0
                        ) - player.get("avg_score", 0)
                    break

            if user_ranking_data:
                group_rankings.append(user_ranking_data)
            else:
                group_rankings.append(
                    {
                        "group_id": group_doc.id,
                        "group_name": group_data.get("name", "N/A"),
                        "rank": "N/A",
                        "points": 0,
                        "form": [],
                    }
                )
        return group_rankings

    @staticmethod
    def _get_player_info(player_ref: Any, users_map: Dict[str, Any]) -> Dict[str, Any]:
        """Return a dictionary with player info."""
        player_data = users_map.get(player_ref.id)
        if not player_data:
            return {"id": player_ref.id, "username": "Unknown", "thumbnail_url": ""}
        return {
            "id": player_ref.id,
            "username": player_data.get("username", "Unknown"),
            "thumbnail_url": player_data.get("thumbnail_url", ""),
        }

    @staticmethod
    def format_matches_for_profile(
        db: Client,
        display_items: List[Dict[str, Any]],
        user_id: str,
        profile_user_data: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """Format matches for the public profile view."""
        # Collect all user refs needed for batch fetching
        needed_refs = set()
        for item in display_items:
            data = item["data"]
            match_type = data.get("matchType", "singles")
            if match_type == "doubles":
                needed_refs.update(data.get("team1", []))
                needed_refs.update(data.get("team2", []))
            else:
                if data.get("player1Ref"):
                    needed_refs.add(data.get("player1Ref"))
                if data.get("player2Ref"):
                    needed_refs.add(data.get("player2Ref"))

        # Fetch all unique users in one batch
        unique_refs_list = list(needed_refs)
        users_map = {}
        if unique_refs_list:
            users_docs = db.get_all(unique_refs_list)
            users_map = {doc.id: doc.to_dict() for doc in users_docs if doc.exists}

        def get_username(ref: Any, default: str = "Unknown") -> str:
            if not ref:
                return default
            u_data = users_map.get(ref.id)
            if u_data:
                return u_data.get("username", default)
            return default

        final_matches = []
        for item in display_items:
            data = item["data"]
            m_id = item["doc"].id
            match_type = data.get("matchType", "singles")

            # Construct object compatible with template
            match_obj = {
                "id": m_id,
                "match_date": data.get("matchDate"),
                "player1_score": data.get("player1Score", 0),
                "player2_score": data.get("player2Score", 0),
                "player1_id": "",
                "player1": {"username": "Unknown"},
                "player2": {"id": "", "username": "Unknown"},
            }

            if match_type == "doubles":
                team1_refs = data.get("team1", [])
                team2_refs = data.get("team2", [])
                in_team1 = any(ref.id == user_id for ref in team1_refs)

                if in_team1:
                    # Profile user is in Team 1 (Player 1 slot)
                    match_obj["player1_id"] = user_id
                    match_obj["player1"] = {
                        "id": user_id,
                        "username": profile_user_data.get("username"),
                    }

                    # Opponent is Team 2 (Player 2 slot)
                    opp_name = "Unknown Team"
                    opp_id = ""
                    if team2_refs:
                        opp_ref = team2_refs[0]
                        opp_id = opp_ref.id
                        opp_name = get_username(opp_ref)
                        if len(team2_refs) > 1 or len(team1_refs) > 1:
                            opp_name += " (Doubles)"

                    match_obj["player2"] = {"id": opp_id, "username": opp_name}

                else:
                    # Profile user is in Team 2 (Player 2 slot)
                    match_obj["player1_id"] = ""  # Not profile user

                    # Opponent is Team 1 (Player 1 slot)
                    opp_name = "Unknown Team"
                    opp_id = ""
                    if team1_refs:
                        opp_ref = team1_refs[0]
                        opp_id = opp_ref.id
                        opp_name = get_username(opp_ref)
                        if len(team1_refs) > 1 or len(team2_refs) > 1:
                            opp_name += " (Doubles)"

                    match_obj["player1"] = {"id": opp_id, "username": opp_name}
                    match_obj["player2"] = {
                        "id": user_id,
                        "username": profile_user_data.get("username"),
                    }

            else:
                # Singles
                p1_ref = data.get("player1Ref")
                p2_ref = data.get("player2Ref")

                if p1_ref and p1_ref.id == user_id:
                    match_obj["player1_id"] = user_id
                    match_obj["player1"] = {
                        "id": user_id,
                        "username": profile_user_data.get("username"),
                    }

                    opp_name = get_username(p2_ref)
                    opp_id = p2_ref.id if p2_ref else ""
                    match_obj["player2"] = {"id": opp_id, "username": opp_name}
                else:
                    match_obj["player1_id"] = p1_ref.id if p1_ref else ""
                    opp_name = get_username(p1_ref)
                    opp_id = p1_ref.id if p1_ref else ""
                    match_obj["player1"] = {"id": opp_id, "username": opp_name}

                    match_obj["player2"] = {
                        "id": user_id,
                        "username": profile_user_data.get("username"),
                    }

            final_matches.append(match_obj)
        return final_matches

    @staticmethod
    def format_matches_for_dashboard(
        db: Client, matches_docs: List[Any], user_id: str
    ) -> List[Dict[str, Any]]:
        """Format matches for the API dashboard view."""
        # Batch fetch user data for all players in the recent matches
        player_refs = set()
        for match_doc in matches_docs:
            match = match_doc.to_dict()
            if match is None:
                continue
            if match.get("player1Ref"):
                player_refs.add(match["player1Ref"])
            if match.get("player2Ref"):
                player_refs.add(match["player2Ref"])
            for ref in match.get("team1", []):
                player_refs.add(ref)
            for ref in match.get("team2", []):
                player_refs.add(ref)

        users_map = {}
        if player_refs:
            user_docs = db.get_all(list(player_refs))
            users_map = {doc.id: doc.to_dict() for doc in user_docs if doc.exists}

        matches_data = []
        for match_doc in matches_docs:
            match = match_doc.to_dict()
            if match is None:
                continue
            p1_score = match.get("player1Score", 0)
            p2_score = match.get("player2Score", 0)
            winner = "player1" if p1_score > p2_score else "player2"

            user_result = "draw"
            if p1_score != p2_score:
                user_won = False
                if match.get("matchType") == "doubles":
                    team1_refs = match.get("team1", [])
                    in_team1 = any(ref.id == user_id for ref in team1_refs)
                    if (in_team1 and winner == "player1") or (
                        not in_team1 and winner == "player2"
                    ):
                        user_won = True
                else:
                    is_player1 = (
                        match.get("player1Ref") and match["player1Ref"].id == user_id
                    )
                    if (is_player1 and winner == "player1") or (
                        not is_player1 and winner == "player2"
                    ):
                        user_won = True
                user_result = "win" if user_won else "loss"

            player1_info: Any
            player2_info: Any
            if match.get("matchType") == "doubles":
                player1_info = [
                    UserService._get_player_info(ref, users_map)
                    for ref in match.get("team1", [])
                ]
                player2_info = [
                    UserService._get_player_info(ref, users_map)
                    for ref in match.get("team2", [])
                ]
            else:
                player1_info = UserService._get_player_info(
                    match["player1Ref"], users_map
                )
                player2_info = UserService._get_player_info(
                    match["player2Ref"], users_map
                )

            matches_data.append(
                {
                    "id": match_doc.id,
                    "player1": player1_info,
                    "player2": player2_info,
                    "player1_score": p1_score,
                    "player2_score": p2_score,
                    "winner": winner,
                    "date": match.get("matchDate", "N/A"),
                    "is_group_match": bool(match.get("groupId")),
                    "match_type": match.get("matchType", "singles"),
                    "user_result": user_result,
                }
            )
        return matches_data
