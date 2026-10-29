## 2024-05-18 - Concurrent Data Fetching
**Learning:** The application uses Google Cloud Firestore, and the `Client` object is thread-safe for reading.
**Action:** Use `ThreadPoolExecutor` to fetch independent data sources concurrently, which can significantly reduce latency. Use `executor.map(func, iterable)` when order matters, or explicit `executor.submit` calls when there are disparate functions. Ensure all arguments (especially kwargs) are explicitly passed when using `executor.submit`.

## 2024-05-18 - Handling Flask Dependencies in Scripts
**Learning:** When using `Faker` inside Flask routes (like the `generate_users` test route in `admin/routes.py`), be aware that in production environments where development dependencies are not installed, this will throw a `ModuleNotFoundError` during CI checks if imported globally.
**Action:** Use a `try...except ImportError` block at the top of the file to gracefully degrade when dev dependencies are missing, setting the module to `None`. Check for `None` inside the route before using it.
