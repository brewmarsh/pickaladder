from typing import Any

from firebase_admin import firestore

from .core import smart_display_name as _smart_display_name

__all__ = ["UserService", "firestore"]


class UserService:
    """Service class for user-related operations and Firestore interaction."""

    smart_display_name = staticmethod(_smart_display_name)

    @staticmethod
    def update_user_profile(*args, **kwargs) -> Any:
        from .core import update_user_profile

        return update_user_profile(*args, **kwargs)

    @staticmethod
    def get_user_by_id(*args, **kwargs) -> Any:
        from .core import get_user_by_id

        return get_user_by_id(*args, **kwargs)

    @staticmethod
    def get_user_friends(*args, **kwargs) -> Any:
        from .friendship import get_user_friends

        return get_user_friends(*args, **kwargs)

    @staticmethod
    def get_user_matches(*args, **kwargs) -> Any:
        from .match_stats import get_user_matches

        return get_user_matches(*args, **kwargs)

    @staticmethod
    def merge_ghost_user(*args, **kwargs) -> Any:
        from .merging import merge_ghost_user

        return merge_ghost_user(*args, **kwargs)

    @staticmethod
    def merge_users(*args, **kwargs) -> Any:
        from .merging import merge_users

        return merge_users(*args, **kwargs)

    @staticmethod
    def _migrate_ghost_references(*args, **kwargs) -> Any:
        from .merging import _migrate_user_references

        return _migrate_user_references(*args, **kwargs)

    @staticmethod
    def _migrate_singles_matches(*args, **kwargs) -> Any:
        from .merging import _migrate_singles_matches

        return _migrate_singles_matches(*args, **kwargs)

    @staticmethod
    def _migrate_doubles_matches(*args, **kwargs) -> Any:
        from .merging import _migrate_doubles_matches

        return _migrate_doubles_matches(*args, **kwargs)

    @staticmethod
    def _migrate_groups(*args, **kwargs) -> Any:
        from .merging import _migrate_groups

        return _migrate_groups(*args, **kwargs)

    @staticmethod
    def _migrate_tournaments(*args, **kwargs) -> Any:
        from .merging import _migrate_tournaments

        return _migrate_tournaments(*args, **kwargs)

    @staticmethod
    def get_user_groups(*args, **kwargs) -> Any:
        from .activity import get_user_groups

        return get_user_groups(*args, **kwargs)

    @staticmethod
    def get_friendship_info(*args, **kwargs) -> Any:
        from .friendship import get_friendship_info

        return get_friendship_info(*args, **kwargs)

    @staticmethod
    def get_user_pending_requests(*args, **kwargs) -> Any:
        from .friendship import get_user_pending_requests

        return get_user_pending_requests(*args, **kwargs)

    @staticmethod
    def get_pending_tournament_invites(*args, **kwargs) -> Any:
        from .activity import get_pending_tournament_invites

        return get_pending_tournament_invites(*args, **kwargs)

    @staticmethod
    def get_active_tournaments(*args, **kwargs) -> Any:
        from .activity import get_active_tournaments

        return get_active_tournaments(*args, **kwargs)

    @staticmethod
    def get_past_tournaments(*args, **kwargs) -> Any:
        from .activity import get_past_tournaments

        return get_past_tournaments(*args, **kwargs)

    @staticmethod
    def get_user_sent_requests(*args, **kwargs) -> Any:
        from .friendship import get_user_sent_requests

        return get_user_sent_requests(*args, **kwargs)

    @staticmethod
    def get_all_users(*args, **kwargs) -> Any:
        from .core import get_all_users

        return get_all_users(*args, **kwargs)

    @staticmethod
    def _get_player_info(*args, **kwargs) -> Any:
        from .match_stats import _get_player_info

        return _get_player_info(*args, **kwargs)

    @staticmethod
    def _get_match_winner_slot(*args, **kwargs) -> Any:
        from .match_stats import _get_match_winner_slot

        return _get_match_winner_slot(*args, **kwargs)

    @staticmethod
    def _get_user_match_result(*args, **kwargs) -> Any:
        from .match_stats import _get_user_match_result

        return _get_user_match_result(*args, **kwargs)

    @staticmethod
    def _collect_match_refs(*args, **kwargs) -> Any:
        from .match_stats import _collect_match_refs

        return _collect_match_refs(*args, **kwargs)

    @staticmethod
    def _fetch_match_entities(*args, **kwargs) -> Any:
        from .match_stats import _fetch_match_entities

        return _fetch_match_entities(*args, **kwargs)

    @staticmethod
    def _get_profile_match_alignment(*args, **kwargs) -> Any:
        from .match_stats import _get_profile_match_alignment

        return _get_profile_match_alignment(*args, **kwargs)

    @staticmethod
    def format_matches_for_profile(*args, **kwargs) -> Any:
        from .match_stats import format_matches_for_profile

        return format_matches_for_profile(*args, **kwargs)

    @staticmethod
    def get_public_groups(*args, **kwargs) -> Any:
        from .activity import get_public_groups

        return get_public_groups(*args, **kwargs)

    @staticmethod
    def format_matches_for_dashboard(*args, **kwargs) -> Any:
        from .match_stats import format_matches_for_dashboard

        return format_matches_for_dashboard(*args, **kwargs)

    @staticmethod
    def _get_user_match_won_lost(*args, **kwargs) -> Any:
        from .match_stats import _get_user_match_won_lost

        return _get_user_match_won_lost(*args, **kwargs)

    @staticmethod
    def _calculate_streak(*args, **kwargs) -> Any:
        from .match_stats import _calculate_streak

        return _calculate_streak(*args, **kwargs)

    @staticmethod
    def calculate_current_streak(*args, **kwargs) -> Any:
        from .match_stats import calculate_current_streak

        return calculate_current_streak(*args, **kwargs)

    @staticmethod
    def calculate_stats(*args, **kwargs) -> Any:
        from .match_stats import calculate_stats

        return calculate_stats(*args, **kwargs)

    @staticmethod
    def _process_h2h_match(*args, **kwargs) -> Any:
        from .match_stats import _process_h2h_match

        return _process_h2h_match(*args, **kwargs)

    @staticmethod
    def get_h2h_stats(*args, **kwargs) -> Any:
        from .match_stats import get_h2h_stats

        return get_h2h_stats(*args, **kwargs)

    @staticmethod
    def get_recent_opponents(*args, **kwargs) -> Any:
        from .match_stats import get_recent_opponents

        return get_recent_opponents(*args, **kwargs)

    @staticmethod
    def accept_friend_request(*args, **kwargs) -> Any:
        from .friendship import accept_friend_request

        return accept_friend_request(*args, **kwargs)

    @staticmethod
    def cancel_friend_request(*args, **kwargs) -> Any:
        from .friendship import cancel_friend_request

        return cancel_friend_request(*args, **kwargs)

    @staticmethod
    def get_group_rankings(*args, **kwargs) -> Any:
        from .activity import get_group_rankings

        return get_group_rankings(*args, **kwargs)

    @staticmethod
    def check_username_availability(*args, **kwargs) -> Any:
        from .profile import check_username_availability

        return check_username_availability(*args, **kwargs)

    @staticmethod
    def update_email_address(*args, **kwargs) -> Any:
        from .profile import update_email_address

        return update_email_address(*args, **kwargs)

    @staticmethod
    def upload_profile_picture(*args, **kwargs) -> Any:
        from .profile import upload_profile_picture

        return upload_profile_picture(*args, **kwargs)

    @staticmethod
    def process_profile_update(*args, **kwargs) -> Any:
        from .core import process_profile_update

        return process_profile_update(*args, **kwargs)

    @staticmethod
    def get_dashboard_data(*args, **kwargs) -> Any:
        from .dashboard import get_dashboard_data

        return get_dashboard_data(*args, **kwargs)

    @staticmethod
    def get_user_profile_data(*args, **kwargs) -> Any:
        from .activity import get_user_profile_data

        return get_user_profile_data(*args, **kwargs)

    @staticmethod
    def get_community_data(*args, **kwargs) -> Any:
        from .activity import get_community_data

        return get_community_data(*args, **kwargs)

    @staticmethod
    def search_users(*args, **kwargs) -> Any:
        from .core import search_users

        return search_users(*args, **kwargs)

    @staticmethod
    def get_friends_page_data(*args, **kwargs) -> Any:
        from .friendship import get_friends_page_data

        return get_friends_page_data(*args, **kwargs)

    @staticmethod
    def send_friend_request(*args, **kwargs) -> Any:
        from .friendship import send_friend_request

        return send_friend_request(*args, **kwargs)

    @staticmethod
    def create_invite_token(*args, **kwargs) -> Any:
        from .core import create_invite_token

        return create_invite_token(*args, **kwargs)

    @staticmethod
    def update_dashboard_profile(*args, **kwargs) -> Any:
        from .core import update_dashboard_profile

        return update_dashboard_profile(*args, **kwargs)

    @staticmethod
    def update_settings(*args, **kwargs) -> Any:
        from .core import update_settings

        return update_settings(*args, **kwargs)
