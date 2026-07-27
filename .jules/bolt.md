## 2025-02-21 - Avoiding Redundant Database Reads Post-Transaction
**Learning:** In the Python Firebase Admin SDK, `@firestore.transactional` decorated functions can return values. When updating a document in a transaction, if subsequent application logic (such as notifications) requires data from that document, it is a significant performance anti-pattern to perform a separate `document.get()` immediately after the transaction.
**Action:** Always return the fetched `DocumentSnapshot` data (e.g., `doc.to_dict()`) directly from the transaction block so it can be reused in the synchronous control flow, eliminating an entire database round-trip.
## 2025-02-21 - Resolving N+1 Query in `get_team_names`
**Learning:** In `pickaladder/match/services/query.py`, the `get_team_names` method previously performed two sequential `db.collection("teams").document(id).get()` calls to fetch team names, resulting in an N+1 query bottleneck.
**Action:** Replaced sequential queries with a single batch fetch using `db.get_all(refs)`. Mapped the result to a dictionary (`{doc.id: doc for doc in db.get_all(refs)}`) to ensure the correct team documents are assigned safely, regardless of the order they are returned, thus halving the database network overhead for this lookup.
## 2025-02-21 - Optimizing Sequential Database Aggregations
**Learning:** Replacing server-side `count()` aggregations with client-side document streaming to avoid sequential blocking I/O is a severe anti-pattern that drastically increases database cost and risks OOM crashes.
**Action:** The correct approach to optimize multiple independent Firestore `count()` queries is to parallelize them using a thread pool (e.g., `concurrent.futures.ThreadPoolExecutor`), preserving the efficiency of server-side counting while minimizing overall latency.
## 2025-02-21 - Avoiding Redundant Database Queries for Complementary Sets
**Learning:** When fetching sets of data that are complements of each other (like "all valid players" vs "all valid opponents" where the only difference is the current user), doing two separate database queries is a performance anti-pattern.
**Action:** Fetch the inclusive set once, then derive the complementary set in-memory (e.g., using `copy()` and `discard()`) to eliminate a redundant database network request.
## 2025-02-21 - Avoiding Redundant Database Queries in Match Validation
**Learning:** In `MatchValidationService._check_player_validity`, the service fetched candidate player IDs twice: once with `include_user=False` and once with `include_user=True`.
**Action:** Deriving the complement set (`cands`) from the inclusive set (`p1_cands`) via `copy()` and `discard(user_id)` eliminates a duplicate database query and optimizes the validation loop.
## 2025-02-21 - Batching sequential Firestore document updates in stats rollbacks
**Learning:** `MatchCommandService.update_match_score` sequentially triggered up to 10 separate `DocumentReference.update` database writes for a doubles match (decrementing old scores and incrementing new scores for each team and individual user) due to `MatchStatsUpdater.apply_stats_delta` performing immediate writes. Sequential, unbatched writes create a significant network overhead and latency bottleneck in a cloud environment compared to atomic batched writes.
**Action:** Introduced an optional `batch: WriteBatch` argument down the `MatchStatsUpdater.apply_stats_delta` stack. `MatchCommandService.update_match_score` now wraps the entire stats application in a single `WriteBatch`, drastically reducing database write latency by executing up to 10 updates as a single round-trip.

