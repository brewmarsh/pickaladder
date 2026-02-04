"""Utility functions for user management."""

from __future__ import annotations

import datetime
from typing import TYPE_CHECKING, Any, cast

from firebase_admin import firestore
from flask import current_app

if TYPE_CHECKING:
    from google.cloud.firestore_v1.base_document import DocumentSnapshot
    from google.cloud.firestore_v1.client import Client
    from google.cloud.firestore_v1.document import DocumentReference

from pickaladder.utils import mask_email

from .models import User

UPSET_THRESHOLD = 0.25


def merge_ghost_user(db: Client, real_user_ref: DocumentReference, email: str) -> None:
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


def wrap_user(user_data: dict[str, Any] | None, uid: str | None = None) -> User | None:
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


def smart_display_name(user: dict[str, Any]) -> str:
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
    def get_user_by_id(db: Client, user_id: str) -> dict[str, Any] | None:
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
    ) -> tuple[bool, bool]:
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
                friend_data = friend_doc.to_dict()
                if friend_data:
                    status = friend_data.get("status")
                    if status == "accepted":
                        is_friend = True
                    elif status == "pending":
                        friend_request_sent = True
        return is_friend, friend_request_sent

    @staticmethod
    def get_user_friends(
        db: Client, user_id: str, limit: int | None = None
    ) -> list[dict[str, Any]]:
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
        friend_docs = cast(list["DocumentSnapshot"], db.get_all(refs))
        results = []
        for doc in friend_docs:
            if doc.exists:
                data = doc.to_dict()
                if data is not None:
                    results.append({"id": doc.id, **data})
        return results

    @staticmethod
    def get_user_pending_requests(db: Client, user_id: str) -> list[dict[str, Any]]:
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
        request_docs = cast(list["DocumentSnapshot"], db.get_all(refs))
        results = []
        for doc in request_docs:
            if doc.exists:
                data = doc.to_dict()
                if data is not None:
                    results.append({"id": doc.id, **data})
        return results

    @staticmethod
    def get_user_sent_requests(db: Client, user_id: str) -> list[dict[str, Any]]:
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
        request_docs = cast(list["DocumentSnapshot"], db.get_all(refs))
        results = []
        for doc in request_docs:
            if doc.exists:
                data = doc.to_dict()
                if data is not None:
                    results.append({"id": doc.id, **data})
        return results

    @staticmethod
    def get_all_users(
        db: Client,
        current_user_id: str,
        search_term: str | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Fetch all users for discovery."""
        query: Any = db.collection("users")
        if search_term:
            # Firestore doesn't support case-insensitive search natively.
            # This searches for an exact username match prefix.
            query = query.where(
                filter=firestore.FieldFilter("username", ">=", search_term)
            ).where(
                filter=firestore.FieldFilter("username", "<=", search_term + "\uf8ff")
            )
        else:
            query = query.order_by("createdAt", direction=firestore.Query.DESCENDING)

        docs = query.limit(limit + 5).stream()
        users = []
        for doc in docs:
            if doc.id == current_user_id:
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
    ) -> dict[str, Any] | None:
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
    def get_user_matches(db: Client, user_id: str) -> list[DocumentSnapshot]:
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
    def calculate_stats(
        matches: list[DocumentSnapshot], user_id: str
    ) -> dict[str, Any]:
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
    def get_group_rankings(db: Client, user_id: str) -> list[dict[str, Any]]:
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
    def _get_player_info(
        player_ref: DocumentReference, users_map: dict[str, dict[str, Any]]
    ) -> dict[str, Any]:
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
    def _format_doubles_match(
        data: dict[str, Any],
        user_id: str,
        profile_user_data: dict[str, Any],
        users_map: dict[str, dict[str, Any]],
        match_obj: dict[str, Any],
    ) -> None:
        """Helper to format a doubles match for the profile view."""
        t1r, t2r = data.get("team1", []), data.get("team2", [])
        in_t1 = any(r.id == user_id for r in t1r)

        def get_unm(ref: DocumentReference | None) -> str:
            if not ref:
                return "Unknown"
            u_data = users_map.get(ref.id)
            if not u_data:
                return "Unknown"
            return u_data.get("username", "Unknown")

        if in_t1:
            match_obj.update(
                {
                    "player1_id": user_id,
                    "player1": {
                        "id": user_id,
                        "username": profile_user_data.get("username"),
                    },
                }
            )
            opp_ref = t2r[0] if t2r else None
            opp_name = get_unm(opp_ref)
            if len(t2r) > 1 or len(t1r) > 1:
                opp_name += " (Doubles)"
            match_obj["player2"] = {
                "id": opp_ref.id if opp_ref else "",
                "username": opp_name,
            }
        else:
            opp_ref = t1r[0] if t1r else None
            opp_name = get_unm(opp_ref)
            if len(t1r) > 1 or len(t2r) > 1:
                opp_name += " (Doubles)"
            match_obj["player1"] = {
                "id": opp_ref.id if opp_ref else "",
                "username": opp_name,
            }
            match_obj["player2"] = {
                "id": user_id,
                "username": profile_user_data.get("username"),
            }

    @staticmethod
    def _format_singles_match(
        data: dict[str, Any],
        user_id: str,
        profile_user_data: dict[str, Any],
        users_map: dict[str, dict[str, Any]],
        match_obj: dict[str, Any],
    ) -> None:
        """Helper to format a singles match for the profile view."""
        p1r, p2r = data.get("player1Ref"), data.get("player2Ref")

        def get_unm(ref: DocumentReference | None) -> str:
            if not ref:
                return "Unknown"
            u_data = users_map.get(ref.id)
            if not u_data:
                return "Unknown"
            return u_data.get("username", "Unknown")

        if p1r and p1r.id == user_id:
            match_obj.update(
                {
                    "player1_id": user_id,
                    "player1": {
                        "id": user_id,
                        "username": profile_user_data.get("username"),
                    },
                    "player2": {"id": p2r.id if p2r else "", "username": get_unm(p2r)},
                }
            )
        else:
            match_obj.update(
                {
                    "player1_id": p1r.id if p1r else "",
                    "player1": {"id": p1r.id if p1r else "", "username": get_unm(p1r)},
                    "player2": {
                        "id": user_id,
                        "username": profile_user_data.get("username"),
                    },
                }
            )

    @staticmethod
    def format_matches_for_profile(
        db: Client,
        display_items: list[dict[str, Any]],
        user_id: str,
        profile_user_data: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Format matches for the public profile view."""
        needed_refs = set()
        for item in display_items:
            d = item["data"]
            if d.get("matchType") == "doubles":
                needed_refs.update(d.get("team1", []) + d.get("team2", []))
            else:
                if d.get("player1Ref"):
                    needed_refs.add(d.get("player1Ref"))
                if d.get("player2Ref"):
                    needed_refs.add(d.get("player2Ref"))

        u_map: dict[str, dict[str, Any]] = {}
        if needed_refs:
            for d in db.get_all(list(needed_refs)):
                if d.exists:
                    data = d.to_dict()
                    if data is not None:
                        u_map[d.id] = data

        final_matches = []
        for item in display_items:
            d = item["data"]
            m_id = item["doc"].id
            m_date = d.get("matchDate")
            p1s, p2s = d.get("player1Score", 0), d.get("player2Score", 0)
            match_obj = {
                "id": m_id,
                "match_date": m_date,
                "player1_score": p1s,
                "player2_score": p2s,
                "player1_id": "",
                "player1": {"username": "Unknown"},
                "player2": {"id": "", "username": "Unknown"},
            }
            if d.get("matchType") == "doubles":
                UserService._format_doubles_match(
                    d, user_id, profile_user_data, u_map, match_obj
                )
            else:
                UserService._format_singles_match(
                    d, user_id, profile_user_data, u_map, match_obj
                )
            final_matches.append(match_obj)
        return final_matches

    @staticmethod
    def _calculate_user_result(match: dict[str, Any], winner: str, user_id: str) -> str:
        """Calculate the result of a match for a specific user."""
        p1_score = match.get("player1Score", 0)
        p2_score = match.get("player2Score", 0)
        if p1_score == p2_score:
            return "draw"

        user_won = False
        if match.get("matchType") == "doubles":
            team1_refs = match.get("team1", [])
            in_team1 = any(ref.id == user_id for ref in team1_refs)
            if (in_team1 and winner == "player1") or (
                not in_team1 and winner == "player2"
            ):
                user_won = True
        else:
            p1_ref = match.get("player1Ref")
            is_player1 = p1_ref and p1_ref.id == user_id
            if (is_player1 and winner == "player1") or (
                not is_player1 and winner == "player2"
            ):
                user_won = True
        return "win" if user_won else "loss"

    @staticmethod
    def _is_match_upset(
        match: dict[str, Any],
        winner: str,
        p1_info: dict[str, Any] | list[dict[str, Any]],
        p2_info: dict[str, Any] | list[dict[str, Any]],
        users_map: dict[str, dict[str, Any]],
    ) -> bool:
        """Determine if a match was an upset based on DUPR ratings."""
        if match.get("is_upset"):
            return True

        def get_single_player(
            info: dict[str, Any] | list[dict[str, Any]],
        ) -> dict[str, Any] | None:
            return info if not isinstance(info, list) else (info[0] if info else None)

        winner_player = get_single_player(p1_info if winner == "player1" else p2_info)
        loser_player = get_single_player(p2_info if winner == "player1" else p1_info)

        if winner_player and loser_player:
            winner_data = users_map.get(winner_player["id"], {})
            loser_data = users_map.get(loser_player["id"], {})
            winner_rating = float(winner_data.get("duprRating") or 0.0)
            loser_rating = float(loser_data.get("duprRating") or 0.0)
            if winner_rating > 0 and loser_rating > 0:
                return (loser_rating - winner_rating) >= UPSET_THRESHOLD
        return False

    @staticmethod
    def format_matches_for_dashboard(
        db: Client, matches_docs: list[DocumentSnapshot], user_id: str
    ) -> list[dict[str, Any]]:
        """Format matches for the API dashboard view."""
        player_refs, team_refs = set(), set()
        for match_doc in matches_docs:
            m = match_doc.to_dict()
            if m is None:
                continue
            if m.get("player1Ref"):
                player_refs.add(m["player1Ref"])
            if m.get("player2Ref"):
                player_refs.add(m["player2Ref"])
            player_refs.update(m.get("team1", []))
            player_refs.update(m.get("team2", []))
            if m.get("team1Ref"):
                team_refs.add(m["team1Ref"])
            if m.get("team2Ref"):
                team_refs.add(m["team2Ref"])

        u_map: dict[str, dict[str, Any]] = {}
        if player_refs:
            for d in db.get_all(list(player_refs)):
                if d.exists:
                    data = d.to_dict()
                    if data is not None:
                        u_map[d.id] = data

        t_map: dict[str, dict[str, Any]] = {}
        if team_refs:
            for d in db.get_all(list(team_refs)):
                if d.exists:
                    data = d.to_dict()
                    if data is not None:
                        t_map[d.id] = data

        matches_data = []
        for match_doc in matches_docs:
            m = match_doc.to_dict()
            if m is None:
                continue
            p1s, p2s = m.get("player1Score", 0), m.get("player2Score", 0)
            winner = "player1" if p1s > p2s else "player2"
            u_res = UserService._calculate_user_result(m, winner, user_id)

            p1i: dict[str, Any] | list[dict[str, Any]]
            p2i: dict[str, Any] | list[dict[str, Any]]

            if m.get("matchType") == "doubles":
                p1i = [
                    UserService._get_player_info(r, u_map) for r in m.get("team1", [])
                ]
                p2i = [
                    UserService._get_player_info(r, u_map) for r in m.get("team2", [])
                ]
            else:
                p1_ref = m.get("player1Ref")
                p2_ref = m.get("player2Ref")
                if p1_ref and p2_ref:
                    p1i = UserService._get_player_info(p1_ref, u_map)
                    p2i = UserService._get_player_info(p2_ref, u_map)
                else:
                    # Fallback for singles with missing refs
                    p1i = {"username": "Unknown", "id": ""}
                    p2i = {"username": "Unknown", "id": ""}

            t1r, t2r = m.get("team1Ref"), m.get("team2Ref")
            t1_data = t_map.get(t1r.id) if t1r else None
            t2_data = t_map.get(t2r.id) if t2r else None
            t1o = {"name": t1_data.get("name") if t1_data else None}
            t2o = {"name": t2_data.get("name") if t2_data else None}
            upset = UserService._is_match_upset(m, winner, p1i, p2i, u_map)

            matches_data.append(
                {
                    "id": match_doc.id,
                    "player1": p1i,
                    "player2": p2i,
                    "team1": t1o,
                    "team2": t2o,
                    "player1_score": p1s,
                    "player2_score": p2s,
                    "winner": winner,
                    "date": m.get("matchDate", "N/A"),
                    "is_group_match": bool(m.get("groupId")),
                    "match_type": m.get("matchType", "singles"),
                    "user_result": u_res,
                    "is_upset": upset,
                }
            )
        return matches_data
