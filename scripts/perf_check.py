import logging
import sys
import time
import unittest.mock

from mockfirestore import MockFirestore

from pickaladder import create_app
from pickaladder.match.services import MatchService
from pickaladder.user.services import UserService
from tests.mock_utils import patch_mockfirestore

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Thresholds in seconds
THRESHOLDS = {
    "UserService.get_all_users": 0.5,
    "MatchService.record_match": 0.5,
    "Leaderboard.get_global": 0.1,  # Should be very fast when cached
    "Leaderboard.get_group": 0.1,  # Should be very fast when cached
}


def benchmark_get_all_users(db):
    # Simulated load: add 100 users
    logger.info("  Adding 100 users to mock db...")
    for i in range(100):
        db.collection("users").document(f"user_{i}").set(
            {"username": f"user_{i}", "createdAt": time.time()}
        )

    start_time = time.time()
    UserService.get_all_users(db, limit=50)
    end_time = time.time()
    return end_time - start_time


def benchmark_record_match(db):
    # Prepare dummy data for match recording
    current_user = {"uid": "perf_test_user", "username": "perf_tester"}
    group_id = "perf_test_group"
    match_data = {
        "player_1_id": "player1",
        "player_2_id": "player2",
        "score_p1": 11,
        "score_p2": 8,
        "match_type": "singles",
        "match_date": "2024-01-01",
        "group_id": group_id,
    }

    # Ensure players exist
    db.collection("users").document("perf_test_user").set(
        {"username": "perf_tester", "dupr_id": "D1"}
    )
    db.collection("users").document("player1").set({"username": "p1", "dupr_id": "D2"})
    db.collection("users").document("player2").set({"username": "p2", "dupr_id": "D3"})

    # Create a group and add members
    db.collection("groups").document(group_id).set(
        {
            "name": "Perf Test Group",
            "members": [
                db.collection("users").document("perf_test_user"),
                db.collection("users").document("player1"),
                db.collection("users").document("player2"),
            ],
        }
    )

    start_time = time.time()
    MatchService.record_match(db, match_data, current_user)
    end_time = time.time()
    return end_time - start_time


def benchmark_leaderboards(db):
    from pickaladder.group.services.leaderboard import get_group_leaderboard
    from pickaladder.match.services import MatchService

    group_id = "perf_group_1"
    # Setup some data
    db.collection("groups").document(group_id).set({"name": "Group 1", "members": []})

    # 1. Warm up cache (Miss)
    logger.info("  Warming up leaderboard cache...")
    get_group_leaderboard(group_id)
    MatchService.get_leaderboard_data(db)

    # 2. Benchmark (Hit)
    start_time = time.time()
    get_group_leaderboard(group_id)
    hit_group = time.time() - start_time

    start_time = time.time()
    MatchService.get_leaderboard_data(db)
    hit_global = time.time() - start_time

    return hit_global, hit_group


def main():
    # Patch mockfirestore to support FieldFilter etc.
    patch_mockfirestore()

    from tests.mock_utils import MockBatch

    mock_db = MockFirestore()
    # Monkeypatch batch method which is missing in mockfirestore but used in services
    mock_db.batch = lambda: MockBatch(mock_db)

    # We need to mock firestore.client() to return our mock_db
    # and other firebase components
    with (
        unittest.mock.patch("firebase_admin.firestore.client", return_value=mock_db),
        unittest.mock.patch("firebase_admin.initialize_app"),
        unittest.mock.patch("firebase_admin.auth"),
    ):
        # We need to make sure create_app doesn't fail due to missing config
        # and that it uses our mocked firebase
        app = create_app(
            {"TESTING": True, "SECRET_KEY": "test", "WTF_CSRF_ENABLED": False}
        )
        with app.app_context():
            results = {}

            logger.info("Benchmarking UserService.get_all_users...")
            results["UserService.get_all_users"] = benchmark_get_all_users(mock_db)

            logger.info("Benchmarking MatchService.record_match...")
            results["MatchService.record_match"] = benchmark_record_match(mock_db)

            logger.info("Benchmarking Leaderboards (Cached)...")
            hit_global, hit_group = benchmark_leaderboards(mock_db)
            results["Leaderboard.get_global"] = hit_global
            results["Leaderboard.get_group"] = hit_group

            failed = False
            for name, duration in results.items():
                threshold = THRESHOLDS.get(name)
                status = "PASS" if duration <= threshold else "FAIL"
                logger.info(
                    f"{name}: {duration:.4f}s (Threshold: {threshold}s) -> {status}"
                )
                if duration > threshold:
                    failed = True

            if failed:
                logger.error("Performance check failed!")
                sys.exit(1)
            else:
                logger.info("Performance check passed!")


if __name__ == "__main__":
    main()
