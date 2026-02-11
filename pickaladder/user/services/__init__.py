from firebase_admin import firestore

from .activity import (
    get_active_tournaments as _get_active_tournaments,
)
from .activity import (
    get_community_data as _get_community_data,
)
from .activity import (
    get_group_rankings as _get_group_rankings,
)
from .activity import (
    get_past_tournaments as _get_past_tournaments,
)
from .activity import (
    get_pending_tournament_invites as _get_pending_tournament_invites,
)
from .activity import (
    get_public_groups as _get_public_groups,
)
from .activity import (
    get_user_groups as _get_user_groups,
)
from .activity import (
    get_user_profile_data as _get_user_profile_data,
)
from .core import (
    create_invite_token as _create_invite_token,
)
from .core import (
    get_all_users as _get_all_users,
)
from .core import (
    get_user_by_id as _get_user_by_id,
)
from .core import (
    process_profile_update as _process_profile_update,
)
from .core import (
    search_users as _search_users,
)
from .core import (
    smart_display_name as _smart_display_name,
)
from .core import (
    update_dashboard_profile as _update_dashboard_profile,
)
from .core import (
    update_settings as _update_settings,
)
from .core import (
    update_user_profile as _update_user_profile,
)
from .dashboard import (
    get_dashboard_data as _get_dashboard_data,
)
from .friendship import (
    accept_friend_request as _accept_friend_request,
)
from .friendship import (
    cancel_friend_request as _cancel_friend_request,
)
from .friendship import (
    get_friends_page_data as _get_friends_page_data,
)
from .friendship import (
    get_friendship_info as _get_friendship_info,
)
from .friendship import (
    get_user_friends as _get_user_friends,
)
from .friendship import (
    get_user_pending_requests as _get_user_pending_requests,
)
from .friendship import (
    get_user_sent_requests as _get_user_sent_requests,
)
from .friendship import (
    send_friend_request as _send_friend_request,
)
from .match_stats import (
    _calculate_streak as _calculate_streak,
)
from .match_stats import (
    _collect_match_refs as _collect_match_refs,
)
from .match_stats import (
    _fetch_match_entities as _fetch_match_entities,
)
from .match_stats import (
    _get_match_winner_slot as _get_match_winner_slot,
)
from .match_stats import (
    _get_player_info as _get_player_info,
)
from .match_stats import (
    _get_profile_match_alignment as _get_profile_match_alignment,
)
from .match_stats import (
    _get_user_match_result as _get_user_match_result,
)
from .match_stats import (
    _get_user_match_won_lost as _get_user_match_won_lost,
)
from .match_stats import (
    _process_h2h_match as _process_h2h_match,
)
from .match_stats import (
    calculate_current_streak as _calculate_current_streak,
)
from .match_stats import (
    calculate_stats as _calculate_stats,
)
from .match_stats import (
    format_matches_for_dashboard as _format_matches_for_dashboard,
)
from .match_stats import (
    format_matches_for_profile as _format_matches_for_profile,
)
from .match_stats import (
    get_h2h_stats as _get_h2h_stats,
)
from .match_stats import (
    get_recent_opponents as _get_recent_opponents,
)
from .match_stats import (
    get_user_matches as _get_user_matches,
)
from .merging import (
    _migrate_doubles_matches as _migrate_doubles_matches,
)
from .merging import (
    _migrate_groups as _migrate_groups,
)
from .merging import (
    _migrate_singles_matches as _migrate_singles_matches,
)
from .merging import (
    _migrate_tournaments as _migrate_tournaments,
)
from .merging import (
    _migrate_user_references as _migrate_user_references,
)
from .merging import (
    merge_ghost_user as _merge_ghost_user,
)
from .merging import (
    merge_users as _merge_users,
)
from .profile import (
    check_username_availability as _check_username_availability,
)
from .profile import (
    update_email_address as _update_email_address,
)
from .profile import (
    upload_profile_picture as _upload_profile_picture,
)

__all__ = ["UserService", "firestore"]


class UserService:
    """Service class for user-related operations and Firestore interaction."""

    smart_display_name = staticmethod(_smart_display_name)
    update_user_profile = staticmethod(_update_user_profile)
    get_user_by_id = staticmethod(_get_user_by_id)
    get_user_friends = staticmethod(_get_user_friends)
    get_user_matches = staticmethod(_get_user_matches)
    merge_ghost_user = staticmethod(_merge_ghost_user)
    merge_users = staticmethod(_merge_users)
    _migrate_ghost_references = staticmethod(_migrate_user_references)
    _migrate_singles_matches = staticmethod(_migrate_singles_matches)
    _migrate_doubles_matches = staticmethod(_migrate_doubles_matches)
    _migrate_groups = staticmethod(_migrate_groups)
    _migrate_tournaments = staticmethod(_migrate_tournaments)
    get_user_groups = staticmethod(_get_user_groups)
    get_friendship_info = staticmethod(_get_friendship_info)
    get_user_pending_requests = staticmethod(_get_user_pending_requests)
    get_pending_tournament_invites = staticmethod(_get_pending_tournament_invites)
    get_active_tournaments = staticmethod(_get_active_tournaments)
    get_past_tournaments = staticmethod(_get_past_tournaments)
    get_user_sent_requests = staticmethod(_get_user_sent_requests)
    get_all_users = staticmethod(_get_all_users)
    _get_player_info = staticmethod(_get_player_info)
    _get_match_winner_slot = staticmethod(_get_match_winner_slot)
    _get_user_match_result = staticmethod(_get_user_match_result)
    _collect_match_refs = staticmethod(_collect_match_refs)
    _fetch_match_entities = staticmethod(_fetch_match_entities)
    _get_profile_match_alignment = staticmethod(_get_profile_match_alignment)
    format_matches_for_profile = staticmethod(_format_matches_for_profile)
    get_public_groups = staticmethod(_get_public_groups)
    format_matches_for_dashboard = staticmethod(_format_matches_for_dashboard)
    _get_user_match_won_lost = staticmethod(_get_user_match_won_lost)
    _calculate_streak = staticmethod(_calculate_streak)
    calculate_current_streak = staticmethod(_calculate_current_streak)
    calculate_stats = staticmethod(_calculate_stats)
    _process_h2h_match = staticmethod(_process_h2h_match)
    get_h2h_stats = staticmethod(_get_h2h_stats)
    get_recent_opponents = staticmethod(_get_recent_opponents)
    accept_friend_request = staticmethod(_accept_friend_request)
    cancel_friend_request = staticmethod(_cancel_friend_request)
    get_group_rankings = staticmethod(_get_group_rankings)
    check_username_availability = staticmethod(_check_username_availability)
    update_email_address = staticmethod(_update_email_address)
    upload_profile_picture = staticmethod(_upload_profile_picture)
    process_profile_update = staticmethod(_process_profile_update)
    get_dashboard_data = staticmethod(_get_dashboard_data)
    get_user_profile_data = staticmethod(_get_user_profile_data)
    get_community_data = staticmethod(_get_community_data)
    search_users = staticmethod(_search_users)
    get_friends_page_data = staticmethod(_get_friends_page_data)
    send_friend_request = staticmethod(_send_friend_request)
    create_invite_token = staticmethod(_create_invite_token)
    update_dashboard_profile = staticmethod(_update_dashboard_profile)
    update_settings = staticmethod(_update_settings)
