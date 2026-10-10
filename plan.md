1. **Optimize `share_brag` in `pickaladder/user/routes/profile.py`**:
   - Currently, it fetches the user and group documents sequentially using `db.collection("users").document(user_id).get()` and `db.collection("groups").document(group_id).get()`.
   - Update it to use `db.get_all([user_ref, group_ref])` to batch the independent reads, resolving an N+1 latency bottleneck. Wait, `db.get_all` takes an iterable of references.
   - We will do:
     ```python
     user_ref = db.collection("users").document(user_id)
     group_ref = db.collection("groups").document(group_id)
     docs = list(db.get_all([user_ref, group_ref]))
     user_doc = docs[0]
     group_doc = docs[1]
     ```
     This halves the network roundtrips for this route.

2. **Log critical learning in `.jules/bolt.md`**:
   - Add a journal entry noting the anti-pattern of sequential single-document gets for independent entities.

3. **Complete pre-commit steps to ensure proper testing, verification, review, and reflection are done**.

4. **Submit PR**:
   - Title: `⚡ Bolt: [performance improvement]`
   - Branch: `bolt-share-brag-batch`
