"""Hierarchical Standing Aggregator based on USAP Standards."""

from __future__ import annotations

import collections
from typing import Any

H2H_LEVEL = 1
PD_LEVEL = 2
H2H_PD_LEVEL = 3
PF_LEVEL = 4

REASONS = {
    H2H_LEVEL: "H2H",
    PD_LEVEL: "PD",
    H2H_PD_LEVEL: "H2H PD",
    PF_LEVEL: "PF",
}

SINGLES_PARTICIPANT_COUNT = 2


class StandingAggregator:
    """Calculates rankings for a pool of players based on match results."""

    @staticmethod
    def aggregate(participant_ids: list[str], matches: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """
        Main entry point. Aggregates stats and resolves ties.
        Returns a sorted list of stats dicts.
        """
        # 1. Calculate basic stats for all participants
        basic_stats = StandingAggregator._calculate_basic_stats(participant_ids, list(matches))

        # 2. Group by matches won
        groups = collections.defaultdict(list)
        for uid, stat in basic_stats.items():
            groups[stat["wins"]].append(stat)

        # 3. Sort groups and resolve ties within each
        sorted_standings = []
        # Sort keys (wins) descending
        for wins in sorted(groups.keys(), reverse=True):
            tied_group = groups[wins]
            if len(tied_group) > 1:
                resolved = StandingAggregator._resolve_ties(tied_group, list(matches))
                sorted_standings.extend(resolved)
            else:
                sorted_standings.append(tied_group[0])

        return sorted_standings

    @staticmethod
    def _calculate_basic_stats(participant_ids: list[str], matches: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
        """Compute wins, losses, PF, PA, PD for each player."""
        stats = {
            uid: {
                "uid": uid,
                "wins": 0,
                "losses": 0,
                "points_for": 0,
                "points_against": 0,
                "matches_played": 0,
                "tie_break_reason": None
            }
            for uid in participant_ids
        }

        for m in matches:
            if m.get("status") != "COMPLETED":
                continue

            # Robust winner detection
            w_id = StandingAggregator._get_w_id(m)
            p1_id = StandingAggregator._get_p_id(m, 1)
            p2_id = StandingAggregator._get_p_id(m, 2)

            s1 = int(m.get("player1Score", 0))
            s2 = int(m.get("player2Score", 0))

            # Record stats
            for uid in [p1_id, p2_id]:
                if uid and uid in stats:
                    stats[uid]["matches_played"] += 1
                    if uid == w_id:
                        stats[uid]["wins"] += 1
                    else:
                        stats[uid]["losses"] += 1

                    if uid == p1_id:
                        stats[uid]["points_for"] += s1
                        stats[uid]["points_against"] += s2
                    else:
                        stats[uid]["points_for"] += s2
                        stats[uid]["points_against"] += s1

        # Calculate final PD and win %
        for s in stats.values():
            s["point_diff"] = s["points_for"] - s["points_against"]
            total = s["wins"] + s["losses"]
            s["win_percentage"] = (s["wins"] / total * 100) if total > 0 else 0

        return stats

    @staticmethod
    def _resolve_ties(tied_players: list[dict[str, Any]], matches: list[dict[str, Any]], hierarchy_level: int = H2H_LEVEL) -> list[dict[str, Any]]:
        """Recursive tie-breaker."""
        if len(tied_players) <= 1 or hierarchy_level > PF_LEVEL:
            return tied_players

        # 1. H2H (Wins among tied players)
        if hierarchy_level == H2H_LEVEL:
            h2h_wins = StandingAggregator._calculate_h2h_wins(tied_players, matches)
            groups = collections.defaultdict(list)
            for p in tied_players:
                groups[h2h_wins[p["uid"]]].append(p)
            return StandingAggregator._process_groups(groups, matches, hierarchy_level)

        # 2. Point Differential (All Games)
        if hierarchy_level == PD_LEVEL:
            groups = collections.defaultdict(list)
            for p in tied_players:
                groups[p["point_diff"]].append(p)
            return StandingAggregator._process_groups(groups, matches, hierarchy_level)

        # 3. H2H Point Differential
        if hierarchy_level == H2H_PD_LEVEL:
            h2h_pd = StandingAggregator._calculate_h2h_pd(tied_players, matches)
            groups = collections.defaultdict(list)
            for p in tied_players:
                groups[h2h_pd[p["uid"]]].append(p)
            return StandingAggregator._process_groups(groups, matches, hierarchy_level)

        # 4. Total Points Scored
        if hierarchy_level == PF_LEVEL:
            groups = collections.defaultdict(list)
            for p in tied_players:
                groups[p["points_for"]].append(p)
            return StandingAggregator._process_groups(groups, matches, hierarchy_level)

        return tied_players

    @staticmethod
    def _process_groups(groups: dict[Any, list[dict[str, Any]]], matches: list[dict[str, Any]], current_level: int) -> list[dict[str, Any]]:
        """Helper to iterate through grouped ties and recurse or move to next level."""
        # If this level didn't break ANY ties (everyone is still in one bucket)
        if len(groups) == 1:
            return StandingAggregator._resolve_ties(list(groups.values())[0], matches, hierarchy_level=current_level + 1)

        sorted_result = []
        sorted_keys = sorted(groups.keys(), reverse=True)

        for val in sorted_keys:
            sub_group = groups[val]

            # Since len(groups) > 1, this level HAS broken a tie for these players
            for player in sub_group:
                # Set reason if not already set by a higher priority breaker
                if player["tie_break_reason"] is None:
                    player["tie_break_reason"] = REASONS.get(current_level)

            if len(sub_group) > 1:
                # RESET to level 1 for the remaining tied sub-group
                sorted_result.extend(StandingAggregator._resolve_ties(sub_group, matches, hierarchy_level=H2H_LEVEL))
            else:
                sorted_result.append(sub_group[0])
        return sorted_result

    @staticmethod
    def _get_w_id(m: dict[str, Any]) -> str | None:
        w_id = m.get("winnerId")
        if not w_id:
            return None
        if isinstance(w_id, str):
            return w_id
        if hasattr(w_id, 'id'):
            return w_id.id
        return None

    @staticmethod
    def _get_p_id(m: dict[str, Any], index: int) -> str | None:
        # Check Participants list (highest reliability in mocks/E2E)
        p_ids = m.get("participants") or []
        if len(p_ids) >= index:
            val = p_ids[index-1]
            if isinstance(val, str):
                return val
            if hasattr(val, 'id'):
                return val.id

        ref_key = f"player{index}Ref"
        id_key = f"player{index}Id"
        ref = m.get(ref_key)

        if isinstance(ref, str):
            return ref
        if ref and hasattr(ref, 'id') and isinstance(ref.id, str):
            return ref.id
        uid = m.get(id_key)
        if uid and isinstance(uid, str):
            return uid

        return None

    @staticmethod
    def _calculate_h2h_wins(players: list[dict[str, Any]], matches: list[dict[str, Any]]) -> dict[str, int]:
        uids = {p["uid"] for p in players}
        wins = {uid: 0 for uid in uids}
        for m in matches:
            if m.get("status") != "COMPLETED":
                continue

            w_id = StandingAggregator._get_w_id(m)
            p1 = StandingAggregator._get_p_id(m, 1)
            p2 = StandingAggregator._get_p_id(m, 2)

            match_parts = {p1, p2}
            if match_parts.issubset(uids) and len(match_parts) == SINGLES_PARTICIPANT_COUNT:
                if w_id in wins:
                    wins[w_id] += 1
        return wins

    @staticmethod
    def _calculate_h2h_pd(players: list[dict[str, Any]], matches: list[dict[str, Any]]) -> dict[str, int]:
        uids = {p["uid"] for p in players}
        pd = {uid: 0 for uid in uids}
        for m in matches:
            if m.get("status") != "COMPLETED":
                continue
            p1 = StandingAggregator._get_p_id(m, 1)
            p2 = StandingAggregator._get_p_id(m, 2)

            match_parts = {p1, p2}
            if match_parts.issubset(uids) and len(match_parts) == SINGLES_PARTICIPANT_COUNT:
                s1 = int(m.get("player1Score", 0))
                s2 = int(m.get("player2Score", 0))
                if p1 in pd:
                    pd[p1] += (s1 - s2)
                if p2 in pd:
                    pd[p2] += (s2 - s1)
        return pd
