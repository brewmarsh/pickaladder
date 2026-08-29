## 2025-02-21 - Avoiding Redundant Database Reads Post-Transaction
**Learning:** In the Python Firebase Admin SDK, `@firestore.transactional` decorated functions can return values. When updating a document in a transaction, if subsequent application logic (such as notifications) requires data from that document, it is a significant performance anti-pattern to perform a separate `document.get()` immediately after the transaction.
**Action:** Always return the fetched `DocumentSnapshot` data (e.g., `doc.to_dict()`) directly from the transaction block so it can be reused in the synchronous control flow, eliminating an entire database round-trip.
## 2025-02-21 - Resolving N+1 Query in `get_team_names`
**Learning:** In `pickaladder/match/services/query.py`, the `get_team_names` method previously performed two sequential `db.collection("teams").document(id).get()` calls to fetch team names, resulting in an N+1 query bottleneck.
**Action:** Replaced sequential queries with a single batch fetch using `db.get_all(refs)`. Mapped the result to a dictionary (`{doc.id: doc for doc in db.get_all(refs)}`) to ensure the correct team documents are assigned safely, regardless of the order they are returned, thus halving the database network overhead for this lookup.
## 2025-02-21 - Optimizing Sequential Database Aggregations
**Learning:** Replacing server-side `count()` aggregations with client-side document streaming to avoid sequential blocking I/O is a severe anti-pattern that drastically increases database cost and risks OOM crashes.
**Action:** The correct approach to optimize multiple independent Firestore `count()` queries is to parallelize them using a thread pool (e.g., `concurrent.futures.ThreadPoolExecutor`), preserving the efficiency of server-side counting while minimizing overall latency.

## 2025-02-21 - Parallelizing Sequential `.count().get()` Aggregations
**Learning:** Sequential `.count().get()` aggregations in Firestore lead to severe N+1 latency problems because each query blocks the main thread waiting for network response.
**Action:** When making multiple independent `.count().get()` aggregations in Firestore, always use `concurrent.futures.ThreadPoolExecutor` to execute them concurrently, drastically reducing overall execution time.

## 2025-02-21 - Avoiding Redundant Database Queries for Complementary Sets
**Learning:** When fetching sets of data that are complements of each other (like "all valid players" vs "all valid opponents" where the only difference is the current user), doing two separate database queries is a performance anti-pattern.
**Action:** Fetch the inclusive set once, then derive the complementary set in-memory (e.g., using `copy()` and `discard()`) to eliminate a redundant database network request.

## 2025-02-21 - Avoiding Redundant Database Queries in Match Validation
**Learning:** In `MatchValidationService._check_player_validity`, the service fetched candidate player IDs twice: once with `include_user=False` and once with `include_user=True`.
**Action:** Deriving the complement set (`cands`) from the inclusive set (`p1_cands`) via `copy()` and `discard(user_id)` eliminates a duplicate database query and optimizes the validation loop.

## 2025-02-21 - Batching sequential Firestore document updates in stats rollbacks
**Learning:** `MatchCommandService.update_match_score` sequentially triggered up to 10 separate `DocumentReference.update` database writes for a doubles match (decrementing old scores and incrementing new scores for each team and individual user) due to `MatchStatsUpdater.apply_stats_delta` performing immediate writes. Sequential, unbatched writes create a significant network overhead and latency bottleneck in a cloud environment compared to atomic batched writes.
**Action:** Introduced an optional `batch: WriteBatch` argument down the `MatchStatsUpdater.apply_stats_delta` stack. `MatchCommandService.update_match_score` now wraps the entire stats application in a single `WriteBatch`, drastically reducing database write latency by executing up to 10 updates as a single round-trip.

## 2025-02-21 - Avoiding Redundant Queries for Candidate Sets
**Learning:** In `pickaladder/match/routes.py` and `pickaladder/match/services/match_validation.py`, `MatchQueryService.get_candidate_player_ids` was being called twice sequentially - once with `include_user=True` and once with `include_user=False`. This caused identical Firestore queries to execute twice, doubling the read overhead during match recording and validation.
**Action:** Always perform the query once (with `include_user=True`) and derive the secondary set in memory using `.copy()` and `.discard(user_id)`.
## 2026-07-23 - Safe parallelization of I/O bound Firebase requests
**Learning:** The `google-cloud-firestore` Python client is thread-safe, making it safe to reuse a single `db` client instance across threads in a `ThreadPoolExecutor`. This is extremely useful for parallelizing independent Firestore operations, such as sequential `.count().get()` queries.
**Action:** When you identify sequential and independent Firestore operations (like aggregations or disjoint queries), use `concurrent.futures.ThreadPoolExecutor` to execute them concurrently, drastically reducing the total latency from a sum of all request times to approximately the longest single request time.

## 2024-05-14 - Prevent Redundant Firestore Queries in Match Validation
**Learning:** In scenarios where one candidate list is a subset of another (e.g., one including the user and one excluding the user), making two identical Firestore queries with slightly different filters is an anti-pattern that creates unnecessary N+1 query bottlenecks.
**Action:** When fetching multiple candidate player sets, query the database once with `include_user=True` and derive the secondary set in-memory by creating a copy and removing the user ID using `.copy()` and `.discard(user_id)`. This prevents redundant reads and improves match recording performance.
## 2025-02-21 - Parallelizing Independent Database Aggregations
**Learning:** Sequential `.count().get()` aggregations on distinct Firestore collections severely degrade performance due to cumulative network round-trips (N+1 query pattern).
**Action:** Always wrap independent `.count()` or single-document `.get()` operations in a `concurrent.futures.ThreadPoolExecutor` when assembling combined dashboard stats to ensure they execute concurrently rather than blocking sequentially.

## 2025-02-21 - Parallelizing Independent Database Queries for Complements
**Learning:** In `pickaladder/match/services/challenge_service.py`, `get_user_challenges` performed two sequential `.get()` queries for sent challenges (`challenger_id == user_id`) and received challenges (`challenged_id == user_id`). This resulted in a sequential latency bottleneck.
**Action:** When making multiple independent disjoint database queries (like sent vs received), use `concurrent.futures.ThreadPoolExecutor` to execute them concurrently, reducing total latency by ~2x.

## 2026-10-23 - Utilizing db.get_all for cross-collection fetches
**Learning:** In the Python `google-cloud-firestore` SDK, `db.get_all()` is extremely powerful because it accepts an iterable of `DocumentReference` objects that can belong to different collections simultaneously (e.g. `[db.collection('users').document(id1), db.collection('groups').document(id2)]`). Previously, I mistakenly assumed it was only useful for fetching multiple documents from the *same* collection.
**Action:** Always prefer `db.get_all()` to batch independent document reads across any collections into a single network request instead of relying on `ThreadPoolExecutor` or sequential `.get()` calls, as it provides the lowest possible latency and overhead.
