## 2024-05-18 - Concurrent Data Fetching
**Learning:** The application uses Google Cloud Firestore, and the `Client` object is thread-safe for reading.
**Action:** Use `ThreadPoolExecutor` to fetch independent data sources concurrently, which can significantly reduce latency. Use `executor.map(func, iterable)` when order matters, or explicit `executor.submit` calls when there are disparate functions. Ensure all arguments (especially kwargs) are explicitly passed when using `executor.submit`.
