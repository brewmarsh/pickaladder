1. **Optimize `share_brag` view in `pickaladder/user/routes/profile.py`**:
   - The view performs two sequential `.get()` operations on the Firestore database: one for the user document and one for the group document.
   - I will use `concurrent.futures.ThreadPoolExecutor` to fetch both documents concurrently, reducing latency, as learned in `bolt.md`.
2. **Complete pre-commit steps to ensure proper testing, verification, review, and reflection are done**:
   - Run `pre_commit_instructions` to ensure linting and testing passes.
3. **Submit PR**:
   - Use `submit` with a clear title and description explaining the performance optimization.
