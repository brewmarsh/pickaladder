from pickaladder.tournament.services.generator import TournamentGenerator


def test_rr_even() -> None:
    ids = ["p1", "p2", "p3", "p4"]
    pairs = TournamentGenerator._get_RR_pair_ids(ids)

    # 4 participants -> 3 rounds, 2 matches per round = 6 matches total
    assert len(pairs) == 6

    # Check for duplicates (regardless of order in tuple)
    normalized_pairs = [tuple(sorted(p)) for p in pairs if p[0] and p[1]]  # type: ignore
    assert len(set(normalized_pairs)) == 6

    # Check everyone plays everyone
    for i in range(len(ids)):
        for j in range(i + 1, len(ids)):
            assert tuple(sorted((ids[i], ids[j]))) in normalized_pairs


def test_rr_odd() -> None:
    ids = ["p1", "p2", "p3", "p4", "p5"]
    pairs = TournamentGenerator._get_RR_pair_ids(ids)

    # 5 participants -> 6 slots (one is None) -> 5 rounds, 3 matches/round = 15 slots
    assert len(pairs) == 15

    # Real matches (no None)
    real_matches = [
        tuple(sorted(p))  # type: ignore
        for p in pairs
        if p[0] is not None and p[1] is not None
    ]
    assert len(real_matches) == 10  # 5 * 4 / 2

    # Check for duplicates
    assert len(set(real_matches)) == 10

    # Check everyone plays everyone
    for i in range(len(ids)):
        for j in range(i + 1, len(ids)):
            assert tuple(sorted((ids[i], ids[j]))) in real_matches


def test_rr_small() -> None:
    ids = ["p1", "p2"]
    pairs = TournamentGenerator._get_RR_pair_ids(ids)
    assert len(pairs) == 1
    assert tuple(sorted(pairs[0])) == ("p1", "p2")  # type: ignore


def test_rr_empty() -> None:
    assert TournamentGenerator.generate_round_robin([]) == []
    assert TournamentGenerator.generate_round_robin(["p1"]) == []
