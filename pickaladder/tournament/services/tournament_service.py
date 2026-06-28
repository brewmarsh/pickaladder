from __future__ import annotations

import logging
import math
from typing import TYPE_CHECKING, Any, cast

from firebase_admin import firestore

from pickaladder.services.mail_service import MailService

from .base import TournamentBase
from .invites import TournamentInvites
from .teams import TournamentTeams

if TYPE_CHECKING:
    from google.cloud.firestore_v1.client import Client

MIN_PARTICIPANTS = 2


class TournamentService(TournamentInvites, TournamentTeams, TournamentBase):
    """Handles business logic and data access for tournaments."""

    @staticmethod
    def handle_match_completion(
        db: Client,
        t_id: str,
        match_data: dict[str, Any],
        winner_uid: str,
    ) -> None:
        """Triggered when a tournament match is completed to advance the winner."""
        # Ensure we have the necessary bracket metadata (round, position)
        if "round" not in match_data or "bracketPosition" not in match_data:
            if mid := match_data.get("id"):
                doc = db.collection("matches").document(mid).get()
                if doc.exists:
                    match_data = {**doc.to_dict(), "id": mid}

        tournament = TournamentService.get_tournament(t_id, db=db)
        fmt = str(tournament.get("format", "ROUND_ROBIN")).upper()

        if fmt in ["SINGLE_ELIMINATION", "DOUBLE_ELIMINATION"]:
            # Handle Grand Final Reset
            if match_data.get("isGrandFinal") and fmt == "DOUBLE_ELIMINATION":
                if TournamentService._check_grand_final_reset(
                    db,
                    t_id,
                    match_data,
                    winner_uid,
                ):
                    return

            # Advance Winner
            TournamentService._advance_winner(db, t_id, match_data, winner_uid)

            # Handle Loser for Double Elimination
            if (
                fmt == "DOUBLE_ELIMINATION"
                and match_data.get("bracketType") == "WINNERS"
            ):
                TournamentService._drop_loser(db, t_id, match_data)

    @staticmethod
    def _check_grand_final_reset(
        db: Client,
        t_id: str,
        match_data: dict[str, Any],
        winner_uid: str,
    ) -> bool:
        """Check if a bracket reset match is needed and create it if so."""
        p1_ref = match_data.get("player1Ref")
        p2_ref = match_data.get("player2Ref")
        if not p1_ref or not p2_ref:
            return False

        # If loser-bracket player (p2) wins, we need a reset match
        if p2_ref.id == winner_uid and not match_data.get("isResetMatch"):
            reset_match = {
                "tournamentId": t_id,
                "round": match_data["round"],
                "bracketPosition": 1,
                "bracketType": "FINALS",
                "isGrandFinal": True,
                "isResetMatch": True,
                "player1Ref": p1_ref,
                "player2Ref": p2_ref,
                "participants": [p1_ref.id, p2_ref.id],
                "matchType": match_data.get("matchType", "singles"),
                "status": "DRAFT",
                "createdAt": firestore.SERVER_TIMESTAMP,
            }
            db.collection("matches").add(reset_match)
            return True
        return False

    @staticmethod
    def _advance_winner(
        db: Client,
        t_id: str,
        match_data: dict[str, Any],
        winner_uid: str,
    ) -> None:
        """Calculate and update the next match in the Winners bracket."""
        current_round = match_data.get("round")
        if current_round is None:
            return

        current_pos = match_data.get("bracketPosition", 0)
        bracket_type = match_data.get("bracketType", "WINNERS")

        next_round = current_round + 1
        next_pos = math.floor(current_pos / 2)
        is_player_1 = current_pos % 2 == 0

        query = (
            db.collection("matches")
            .where(filter=firestore.FieldFilter("tournamentId", "==", t_id))
            .where(filter=firestore.FieldFilter("round", "==", next_round))
            .where(filter=firestore.FieldFilter("bracketPosition", "==", next_pos))
            .where(filter=firestore.FieldFilter("bracketType", "==", bracket_type))
            .limit(1)
        )

        next_match_snap = list(query.stream())
        winner_ref = db.collection("users").document(winner_uid)

        if next_match_snap:
            match_id = next_match_snap[0].id
            field = "player1Ref" if is_player_1 else "player2Ref"
            db.collection("matches").document(match_id).update(
                {field: winner_ref, "participants": firestore.ArrayUnion([winner_uid])},
            )
        elif bracket_type == "WINNERS":
            TournamentService._push_to_finals(db, t_id, winner_uid, is_winners=True)
        elif bracket_type == "LOSERS":
            TournamentService._push_to_finals(db, t_id, winner_uid, is_winners=False)

    @staticmethod
    def _push_to_finals(
        db: Client,
        t_id: str,
        winner_uid: str,
        is_winners: bool,
    ) -> None:
        """Push a bracket winner to the Grand Finals match."""
        query = (
            db.collection("matches")
            .where(filter=firestore.FieldFilter("tournamentId", "==", t_id))
            .where(filter=firestore.FieldFilter("bracketType", "==", "FINALS"))
            .limit(1)
        )
        finals_snap = list(query.stream())
        if finals_snap:
            winner_ref = db.collection("users").document(winner_uid)
            field = "player1Ref" if is_winners else "player2Ref"
            db.collection("matches").document(finals_snap[0].id).update(
                {field: winner_ref, "participants": firestore.ArrayUnion([winner_uid])},
            )

    @staticmethod
    def _drop_loser(db: Client, t_id: str, match_data: dict[str, Any]) -> None:
        """Logic for moving the loser to the Losers bracket (Double Elimination)."""
        current_round = match_data.get("round")
        current_pos = match_data.get("bracketPosition", 0)
        if current_round is None:
            return

        # DE Formula: 1->1, 2->2, 3->4, 4->6...
        next_round = 1 if current_round == 1 else (2 * current_round) - 2

        from pickaladder.tournament.services.generator import TournamentGenerator

        t_data = TournamentService.get_tournament(t_id, db=db)
        p_count = len(t_data.get("participant_ids", []))
        bracket_size = TournamentGenerator._next_power_of_2(p_count)

        num_winners_matches = bracket_size // (2**current_round)
        next_pos = (num_winners_matches - 1) - current_pos

        query = (
            db.collection("matches")
            .where(filter=firestore.FieldFilter("tournamentId", "==", t_id))
            .where(filter=firestore.FieldFilter("round", "==", next_round))
            .where(filter=firestore.FieldFilter("bracketPosition", "==", next_pos))
            .where(filter=firestore.FieldFilter("bracketType", "==", "LOSERS"))
            .limit(1)
        )

        target_snap = list(query.stream())
        if target_snap:
            loser_uid = match_data.get("loserId")
            if not loser_uid:
                return
            loser_ref = db.collection("users").document(loser_uid)
            db.collection("matches").document(target_snap[0].id).update(
                {
                    "player2Ref": loser_ref,
                    "participants": firestore.ArrayUnion([loser_uid]),
                },
            )

    @staticmethod
    def _build_create_payload(
        data: dict[str, Any],
        user_uid: str,
        user_ref: Any,
    ) -> dict[str, Any]:
        """Construct the initial tournament payload."""
        from firebase_admin import firestore

        m_type = data.get("matchType") or (data.get("mode") or "singles").lower()
        return {
            "name": data["name"],
            "date": data["date"],
            "venue_name": data.get("venue_name"),
            "address": data.get("address"),
            "matchType": m_type,
            "mode": m_type.upper(),
            "format": data.get("format", "SINGLE_ELIMINATION"),
            "pool_count": data.get("pool_count", 0),
            "promoted_per_pool": data.get("promoted_per_pool", 0),
            "ownerRef": user_ref,
            "organizer_id": user_uid,
            "status": "Active",
            "participants": [{"userRef": user_ref, "status": "accepted"}],
            "participant_ids": [user_uid],
            "createdAt": firestore.SERVER_TIMESTAMP,
        }

    @staticmethod
    def create_tournament(data: dict[str, Any], user_uid: str) -> str:
        """Create a new tournament in Firestore."""
        from firebase_admin import firestore

        db = firestore.client()
        user_ref = db.collection("users").document(user_uid)
        payload = TournamentService._build_create_payload(data, user_uid, user_ref)

        _, doc_ref = db.collection("tournaments").add(payload)
        return str(doc_ref.id)

    @staticmethod
    def _has_matches(db: Client, t_id: str) -> bool:
        """Check if any matches exist for a tournament."""
        query = (
            db.collection("matches")
            .where(filter=firestore.FieldFilter("tournamentId", "==", t_id))
            .limit(1)
            .stream()
        )
        return any(query)

    @staticmethod
    def _prepare_update_payload(
        db: Client,
        t_id: str,
        update: dict[str, Any],
    ) -> dict[str, Any]:
        """Process and sanitize the update payload."""
        if "start_date" in update:
            update["date"] = update["start_date"]

        if TournamentService._has_matches(db, t_id):
            for f in ["matchType", "mode", "format"]:
                update.pop(f, None)
        return update

    @staticmethod
    def update_tournament(
        t_id: str,
        uid: str,
        update: dict[str, Any],
        db: Client | None = None,
    ) -> None:
        """Update tournament details with ownership check."""
        from firebase_admin import firestore

        db = db or firestore.client()
        ref = db.collection("tournaments").document(t_id)
        doc = cast("Any", ref.get())
        if not doc.exists:
            msg = "Tournament not found."
            raise ValueError(msg)

        data = cast("dict[str, Any]", doc.to_dict())
        TournamentService._validate_tournament_ownership(data, uid)

        payload = TournamentService._prepare_update_payload(db, t_id, update)
        ref.update(payload)

    @staticmethod
    def get_tournament_for_edit(
        t_id: str,
        uid: str,
        db: Client | None = None,
    ) -> dict[str, Any]:
        """Fetch tournament for editing with existence and ownership checks."""
        details = TournamentService.get_tournament_details(t_id, uid, db)
        if not details:
            msg = "Tournament not found."
            raise ValueError(msg)
        return cast("dict[str, Any]", details["tournament"])

    @staticmethod
    def _parse_form_date(val: Any) -> Any:
        """Convert date/datetime from form into appropriate format."""
        import datetime

        if not val:
            msg = "Date is required."
            raise ValueError(msg)
        if isinstance(val, datetime.date) and not isinstance(val, datetime.datetime):
            return datetime.datetime.combine(val, datetime.time.min)
        return val

    @staticmethod
    def _build_form_update_payload(fd: dict[str, Any]) -> dict[str, Any]:
        """Construct update dictionary from form data."""
        dt = TournamentService._parse_form_date(fd.get("start_date"))
        m_type = str(fd.get("match_type") or fd.get("mode") or "singles").lower()
        return {
            "name": fd.get("name"),
            "date": dt,
            "venue_name": fd.get("venue_name"),
            "address": fd.get("address"),
            "matchType": m_type,
            "mode": m_type.upper(),
            "format": fd.get("format", "SINGLE_ELIMINATION"),
            "pool_count": fd.get("pool_count", 0),
            "promoted_per_pool": fd.get("promoted_per_pool", 0),
        }

    @staticmethod
    def update_tournament_from_form(
        t_id: str,
        uid: str,
        fd: dict[str, Any],
        banner: Any = None,
        db: Client | None = None,
    ) -> None:
        """Update tournament using data from TournamentForm."""
        upd = TournamentService._build_form_update_payload(fd)
        if banner and getattr(banner, "filename", None):
            url = TournamentService._upload_banner(t_id, banner)
            if url:
                upd["banner_url"] = url
        TournamentService.update_tournament(t_id, uid, upd, db=db)

    @staticmethod
    def delete_tournament(t_id: str, uid: str, db: Client | None = None) -> None:
        """Delete a tournament if owner."""
        from firebase_admin import firestore

        if db is None:
            db = firestore.client()
        ref = db.collection("tournaments").document(t_id)
        doc = cast("Any", ref.get())
        if (
            not doc.exists
            or TournamentService._get_tournament_owner_id(doc.to_dict() or {}) != uid
        ):
            msg = "Unauthorized"
            raise PermissionError(msg)
        ref.delete()

    @staticmethod
    def _send_participant_email(
        user: dict[str, Any],
        t_data: dict[str, Any],
        winner: str,
        stands: list[dict[str, Any]],
    ) -> None:
        """Internal helper to send email if user has one."""
        if not user.get("email"):
            return
        MailService.send_email(
            to=user["email"],
            subject=f"Results: {t_data['name']}",
            template="email/tournament_results.html",
            user=user,
            tournament=t_data,
            winner_name=winner,
            standings=stands[:3],
        )

    @staticmethod
    def _notify_all_participants(
        data: dict[str, Any],
        winner: str,
        stands: list[dict[str, Any]],
        db: Client | None = None,
    ) -> None:
        """Loop through participants and send result emails using batched queries to prevent N+1."""
        from firebase_admin import firestore

        db = db or firestore.client()

        # 1. Collect all accepted participants and their userRefs
        accepted_participants = []
        u_refs = []

        for p in data.get("participants", []):
            if p and p.get("status") == "accepted":
                u_ref = p.get("userRef")
                if u_ref:
                    accepted_participants.append((p, u_ref))
                    u_refs.append(u_ref)

        if not u_refs:
            return

        # 2. Batch fetch all users
        try:
            user_docs = db.get_all(u_refs)
            user_map = {doc.id: doc for doc in user_docs if doc.exists}
        except Exception:
            logging.exception(
                "Failed to batch fetch users for tournament notifications"
            )
            return

        # 3. Send emails
        for p_data, u_ref in accepted_participants:
            try:
                doc = user_map.get(u_ref.id)
                if doc and (d := doc.to_dict()):
                    TournamentService._send_participant_email(d, data, winner, stands)
            except Exception:
                logging.exception("Email failed")

    @staticmethod
    def complete_tournament(t_id: str, uid: str, db: Client | None = None) -> None:
        """Finalize tournament and send emails."""
        from firebase_admin import firestore

        from pickaladder.tournament.utils import get_tournament_standings

        db = db or firestore.client()
        ref = db.collection("tournaments").document(t_id)
        doc = cast("Any", ref.get())
        if not doc or not doc.exists:
            msg = "Tournament not found"
            raise ValueError(msg)

        data = cast("dict[str, Any]", doc.to_dict())
        TournamentService._validate_tournament_ownership(data, uid)

        ref.update({"status": "Completed"})
        stands = get_tournament_standings(db, t_id, data.get("matchType", "singles"))
        winner = stands[0]["name"] if stands else "No one"
        TournamentService._notify_all_participants(data, winner, stands, db=db)

    @staticmethod
    def _prepare_match_pairing(
        m: dict[str, Any],
        t_id: str,
        t_date: Any,
    ) -> dict[str, Any]:
        """Enrich a match pairing with tournament metadata."""
        m["tournamentId"] = t_id
        m["matchDate"] = m.get("matchDate") or t_date
        return m

    @staticmethod
    def save_pairings(t_id: str, pairings: list[dict[str, Any]]) -> int:
        """Save generated match pairings to the global matches collection."""
        from firebase_admin import firestore

        db = firestore.client()
        t_ref = db.collection("tournaments").document(t_id)
        t_snap = cast("Any", t_ref.get())
        t_data = t_snap.to_dict() or {}
        t_date = t_data.get("date") or firestore.SERVER_TIMESTAMP

        batch = db.batch()
        for m in pairings:
            match_doc = TournamentService._prepare_match_pairing(m, t_id, t_date)
            batch.set(db.collection("matches").document(), match_doc)

        batch.update(t_ref, {"status": "PUBLISHED"})
        batch.commit()
        return len(pairings)

    @staticmethod
    def _get_seeded_participant_ids(db: Client, t_data: dict[str, Any]) -> list[str]:
        """Fetch participant UIDs and sort them by Glicko-2 rating for seeding."""
        participant_ids = t_data.get("participant_ids", [])
        if not participant_ids:
            return []

        user_refs = [db.collection("users").document(uid) for uid in participant_ids]
        user_snaps = db.get_all(user_refs)

        # Pair ID with rating
        ratings = []
        for snap in user_snaps:
            if snap.exists:
                data = snap.to_dict() or {}
                # Use Glicko-2 mu, fallback to ELO, fallback to 1200
                stats = data.get("stats", {})
                rating = (
                    stats.get("glicko2", {}).get("mu") or stats.get("elo") or 1200.0
                )
                ratings.append((snap.id, rating))
            else:
                ratings.append((snap.id, 0.0))

        # Sort by rating descending
        ratings.sort(key=lambda x: x[1], reverse=True)
        return [r[0] for r in ratings]

    @staticmethod
    def _gen_singles_bracket(
        db: Client,
        t_data: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Generate bracket data for singles tournament."""
        participants = TournamentService._resolve_participants(
            db,
            t_data.get("participants", []),
        )
        return [
            {
                "id": p["user"]["id"],
                "name": p["display_name"],
                "type": "player",
                "members": [p["user"]["id"]],
            }
            for p in participants
            if p["status"] == "accepted"
        ]

    @staticmethod
    def _map_team_to_bracket_item(doc: Any) -> dict[str, Any] | None:
        """Map a team document to a bracket item."""
        d = doc.to_dict()
        if not d:
            return None
        return {
            "id": d.get("team_id"),
            "name": d.get("team_name"),
            "type": "team",
            "members": [d.get("p1_uid"), d.get("p2_uid")],
            "tournament_team_id": doc.id,
        }

    @staticmethod
    def _gen_doubles_bracket(db: Client, t_id: str) -> list[dict[str, Any]]:
        """Generate bracket data for doubles tournament."""
        teams = (
            db.collection("tournaments")
            .document(t_id)
            .collection("teams")
            .where(filter=firestore.FieldFilter("status", "==", "CONFIRMED"))
            .stream()
        )
        return [
            item
            for doc in teams
            if (item := TournamentService._map_team_to_bracket_item(doc))
        ]

    @staticmethod
    def generate_bracket(t_id: str, db: Client | None = None) -> list[Any]:
        """Generate a tournament bracket based on participants or teams."""
        from firebase_admin import firestore

        db = db or firestore.client()
        doc = cast("Any", db.collection("tournaments").document(t_id).get())
        if not doc or not doc.exists:
            return []
        t_data = doc.to_dict() or {}
        m_type = (t_data.get("matchType") or t_data.get("mode", "singles")).lower()
        if m_type == "singles":
            return TournamentService._gen_singles_bracket(db, t_data)
        return TournamentService._gen_doubles_bracket(db, t_id)

    @staticmethod
    def publish_bracket(t_id: str, uid: str, db: Client | None = None) -> int:
        """Generate and save the tournament pairings based on the chosen format."""
        from firebase_admin import firestore

        from pickaladder.tournament.services.generator import TournamentGenerator

        db = db or firestore.client()
        t_ref = db.collection("tournaments").document(t_id)
        t_snap = cast("Any", t_ref.get())
        if not t_snap.exists:
            msg = "Tournament not found"
            raise ValueError(msg)

        t_data = t_snap.to_dict() or {}
        TournamentService._validate_tournament_ownership(t_data, uid)

        fmt = t_data.get("format", "ROUND_ROBIN").upper()
        pairings = []

        if fmt == "SINGLE_ELIMINATION":
            seeded_ids = TournamentService._get_seeded_participant_ids(db, t_data)
            pairings = TournamentGenerator.generate_single_elimination(seeded_ids)
        elif fmt == "DOUBLE_ELIMINATION":
            seeded_ids = TournamentService._get_seeded_participant_ids(db, t_data)
            pairings = TournamentGenerator.generate_double_elimination(seeded_ids)
        elif fmt == "POOL_PLAY":
            participant_ids = t_data.get("participant_ids", [])
            pool_count = t_data.get("pool_count", 2)
            pairings = TournamentGenerator.generate_pool_play(
                participant_ids,
                pool_count,
            )
        else:
            # Default to Round Robin
            participant_ids = t_data.get("participant_ids", [])
            pairings = TournamentGenerator.generate_round_robin(participant_ids)

        if not pairings:
            return 0

        return TournamentService.save_pairings(t_id, pairings)

    @staticmethod
    def promote_pools_to_bracket(
        t_id: str,
        uid: str,
        promoted_per_pool: int,
        db: Client | None = None,
    ) -> int:
        """Promote top performers from pools to a single elimination bracket."""
        from firebase_admin import firestore

        from pickaladder.tournament.services.generator import TournamentGenerator
        from pickaladder.tournament.utils import get_tournament_standings

        db = db or firestore.client()
        t_ref = db.collection("tournaments").document(t_id)
        t_snap = cast("Any", t_ref.get())
        if not t_snap.exists:
            msg = "Tournament not found"
            raise ValueError(msg)

        t_data = t_snap.to_dict() or {}
        TournamentService._validate_tournament_ownership(t_data, uid)

        pool_count = t_data.get("pool_count", 0)
        if pool_count < 1:
            msg = "Tournament does not have pools"
            raise ValueError(msg)

        match_type = (t_data.get("matchType") or t_data.get("mode", "singles")).lower()
        pool_labels = [chr(65 + i) for i in range(pool_count)]

        # 1. Extract top players from each pool
        promoted_items = []
        for pool_id in pool_labels:
            stands = get_tournament_standings(db, t_id, match_type, pool_id=pool_id)
            # Get top performers
            for i in range(min(promoted_per_pool, len(stands))):
                promoted_items.append((stands[i]["id"], i))  # (uid, rank_in_pool)

        if not promoted_items:
            return 0

        # 2. Seed promoted players
        # Seeding logic: Rank 1s from all pools first, then Rank 2s, etc.
        promoted_items.sort(key=lambda x: x[1])
        final_seeded_ids = [x[0] for x in promoted_items]

        # 3. Generate and save pairings
        pairings = TournamentGenerator.generate_single_elimination(final_seeded_ids)
        if not pairings:
            return 0

        return TournamentService.save_pairings(t_id, pairings)

    @staticmethod
    def _check_user_in_team(
        user_uid: str,
        team_data: dict[str, Any],
    ) -> tuple[str | None, bool] | None:
        """Check if user is in team and return status/pending flag."""
        if team_data.get("p1_uid") == user_uid or team_data.get("p2_uid") == user_uid:
            is_pending = (
                team_data.get("p2_uid") == user_uid
                and team_data.get("status") == "PENDING"
            )
            return cast("str", team_data.get("status")), is_pending
        return None

    @staticmethod
    def _get_team_status_for_user(
        db: Client,
        t_id: str,
        user_uid: str,
    ) -> tuple[str | None, bool]:
        """Fetch team status and pending flag for a user."""
        teams = db.collection("tournaments").document(t_id).collection("teams").stream()
        for doc in teams:
            res = TournamentService._check_user_in_team(
                user_uid,
                cast("dict[str, Any]", doc.to_dict()),
            )
            if res:
                return res
        return None, False

    @staticmethod
    def get_tournament_details(
        t_id: str,
        uid: str,
        db: Client | None = None,
    ) -> dict[str, Any] | None:
        """Fetch full tournament details including participants and standings."""
        from firebase_admin import firestore

        from pickaladder.tournament.utils import get_tournament_standings
        from pickaladder.user import UserService

        db = db or firestore.client()
        ref = db.collection("tournaments").document(t_id)
        doc = cast("Any", ref.get())
        if not doc or not doc.exists:
            return None

        data = TournamentService._enrich_tournament(doc)
        meta = TournamentBase._get_tournament_metadata(data, uid)

        parts = data.get("participants", [])
        resolved_parts = TournamentService._resolve_participants(db, parts)
        stands = get_tournament_standings(db, t_id, data.get("matchType", "singles"))
        c_ids = TournamentService._extract_participant_ids(parts)
        t_stat, pend = TournamentService._get_team_status_for_user(db, t_id, uid)

        return {
            "tournament": data,
            "participants": resolved_parts,
            "standings": stands,
            "podium": stands[:3] if data.get("status") == "Completed" else [],
            "invitable_users": TournamentService._get_invitable_players(db, uid, c_ids),
            "user_groups": UserService.get_user_groups(db, uid),
            "team_status": t_stat,
            "pending_partner_invite": pend,
            **meta,
        }
