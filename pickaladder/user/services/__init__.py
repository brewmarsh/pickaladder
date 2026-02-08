from firebase_admin import firestore
from .core import (
    get_all_users as _get_all_users,
    get_user_by_id as _get_user_by_id,
    smart_display_name as _smart_display_name,
    update_user_profile as _update_user_profile,
)
from .friendship import (
    get_user_friends as _get_user_friends,
    get_friendship_info as _get_friendship_info,
    get_user_pending_requests as _get_user_pending_requests,
    get_user_sent_requests as _get_user_sent_requests,
    accept_friend_request as _accept_friend_request,
    cancel_friend_request as _cancel_friend_request,
)
from .merging import (
    merge_users as _merge_users,
    merge_ghost_user as _merge_ghost_user,
    _migrate_user_references as _migrate_user_references,
    _migrate_singles_matches as _migrate_singles_matches,
    _migrate_doubles_matches as _migrate_doubles_matches,
    _migrate_groups as _migrate_groups,
    _migrate_tournaments as _migrate_tournaments,
)
from .match_stats import (
    get_user_matches as _get_user_matches,
    calculate_stats as _calculate_stats,
    format_matches_for_dashboard as _format_matches_for_dashboard,
    format_matches_for_profile as _format_matches_for_profile,
    get_h2h_stats as _get_h2h_stats,
    _get_match_winner_slot as _get_match_winner_slot,
    _get_user_match_result as _get_user_match_result,
    _calculate_streak as _calculate_streak,
    _process_h2h_match as _process_h2h_match,
    _fetch_match_entities as _fetch_match_entities,
    _collect_match_refs as _collect_match_refs,
    _get_user_match_won_lost as _get_user_match_won_lost,
    _get_profile_match_alignment as _get_profile_match_alignment,
    _get_player_info as _get_player_info,
)
from .activity import (
    get_active_tournaments as _get_active_tournaments,
    get_past_tournaments as _get_past_tournaments,
    get_user_groups as _get_user_groups,
    get_group_rankings as _get_group_rankings,
    get_pending_tournament_invites as _get_pending_tournament_invites,
    get_public_groups as _get_public_groups,
)


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
    calculate_stats = staticmethod(_calculate_stats)
    _process_h2h_match = staticmethod(_process_h2h_match)
    get_h2h_stats = staticmethod(_get_h2h_stats)
    accept_friend_request = staticmethod(_accept_friend_request)
    cancel_friend_request = staticmethod(_cancel_friend_request)
    get_group_rankings = staticmethod(_get_group_rankings)
