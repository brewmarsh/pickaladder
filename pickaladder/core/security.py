import time
from collections import defaultdict
from functools import wraps
from typing import Any, Callable

from flask import abort, current_app, request

# Simple in-memory storage for rate limiting
# NOTE: This is per-process. In multi-worker environments (gunicorn),
# each worker will have its own counter. For a truly production-grade
# solution, a shared store like Redis should be used.
_rate_limit_storage: dict[str, list[float]] = defaultdict(list)


def rate_limit(limit: int = 5, window: int = 60) -> Callable:
    """
    Rate limiter decorator.

    Args:
        limit (int): Number of allowed requests within the window.
        window (int): Time window in seconds.
    """

    def decorator(f: Callable) -> Callable:
        @wraps(f)
        def wrapped(*args: Any, **kwargs: Any) -> Any:
            # Skip rate limiting in testing if needed, unless explicitly requested
            if current_app.config.get("TESTING") and not current_app.config.get(
                "TEST_RATE_LIMITING",
            ):
                return f(*args, **kwargs)

            # Key by remote address and endpoint
            # We use both to ensure rate limiting is per-user per-endpoint
            key = f"{request.remote_addr}:{request.endpoint}"
            now = time.time()

            # Clean up old requests outside the window
            _rate_limit_storage[key] = [
                t for t in _rate_limit_storage[key] if t > now - window
            ]

            if len(_rate_limit_storage[key]) >= limit:
                current_app.logger.warning(
                    f"Rate limit exceeded for {request.remote_addr} "
                    f"on {request.endpoint}",
                )
                abort(429, description="Too many requests. Please try again later.")

            _rate_limit_storage[key].append(now)
            return f(*args, **kwargs)

        return wrapped

    return decorator
