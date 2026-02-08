"""Tests for the match parser service."""

from __future__ import annotations

import unittest

from pickaladder.group.services.match_parser import _extract_team_ids, _resolve_team_ids


class MockRef:
    def __init__(self, doc_id: str):
        self.id = doc_id


class TestMatchParser(unittest.TestCase):
    """Test case for the match parser service."""

    def test_resolve_team_ids_list_refs(self) -> None:
        data = {"team1": [MockRef("user1"), MockRef("user2")]}
        ids = _resolve_team_ids(data, "team1", "player1", "partner")
        self.assertEqual(ids, {"user1", "user2"})

    def test_resolve_team_ids_list_strings(self) -> None:
        data = {"team1": ["user1", "user2"]}
        ids = _resolve_team_ids(data, "team1", "player1", "partner")
        self.assertEqual(ids, {"user1", "user2"})

    def test_resolve_team_ids_individual_refs(self) -> None:
        data = {"player1Ref": MockRef("user1"), "partnerRef": MockRef("user2")}
        ids = _resolve_team_ids(data, "team1", "player1", "partner")
        self.assertEqual(ids, {"user1", "user2"})

    def test_resolve_team_ids_individual_ids(self) -> None:
        data = {"player1Id": "user1", "partnerId": "user2"}
        ids = _resolve_team_ids(data, "team1", "player1", "partner")
        self.assertEqual(ids, {"user1", "user2"})

    def test_resolve_team_ids_mixed(self) -> None:
        data = {"team1": [MockRef("user1")], "partnerId": "user2"}
        ids = _resolve_team_ids(data, "team1", "player1", "partner")
        self.assertEqual(ids, {"user1", "user2"})

    def test_extract_team_ids_full(self) -> None:
        data = {
            "player1Ref": MockRef("user1"),
            "partnerId": "user2",
            "player2Id": "user3",
            "opponent2Ref": MockRef("user4"),
        }
        t1, t2 = _extract_team_ids(data)
        self.assertEqual(t1, {"user1", "user2"})
        self.assertEqual(t2, {"user3", "user4"})

    def test_extract_team_ids_singles(self) -> None:
        data = {"player1Id": "user1", "player2Id": "user2"}
        t1, t2 = _extract_team_ids(data)
        self.assertEqual(t1, {"user1"})
        self.assertEqual(t2, {"user2"})


if __name__ == "__main__":
    unittest.main()
