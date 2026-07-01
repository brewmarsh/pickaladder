"""Background task execution module."""

from __future__ import annotations

import logging
from concurrent.futures import Future, ThreadPoolExecutor
from typing import TYPE_CHECKING, Any, Callable, TypeVar

if TYPE_CHECKING:
    from flask import Flask

T = TypeVar("T")

logger = logging.getLogger(__name__)


class TaskExecutor:
    """Manager for background task execution using a thread pool."""

    def __init__(self, app: Flask | None = None) -> None:
        self.app = app
        self._executor: ThreadPoolExecutor | None = None
        if app is not None:
            self.init_app(app)

    def init_app(self, app: Flask) -> None:
        """Initialize the executor with Flask app configuration."""
        self.app = app
        max_workers = app.config.get("TASK_EXECUTOR_MAX_WORKERS", 4)
        self._executor = ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix="task_executor",
        )
        app.extensions["task_executor"] = self
        app.logger.info(f"Initialized TaskExecutor with {max_workers} workers")

    def run_async(self, func: Callable[..., T], *args: Any, **kwargs: Any) -> Future[T]:
        """
        Run a function asynchronously in a background thread.

        Ensures the Flask application context is available during execution.
        """
        if self._executor is None or self.app is None:
            msg = "TaskExecutor not initialized with a Flask app"
            raise RuntimeError(msg)

        def wrapper() -> T:
            # nosec B101
            assert self.app is not None  # nosec B101
            with self.app.app_context():
                try:
                    self.app.logger.debug(f"Starting background task: {func.__name__}")
                    result = func(*args, **kwargs)
                    self.app.logger.debug(f"Completed background task: {func.__name__}")
                    return result
                except Exception as e:
                    self.app.logger.error(
                        f"Error in background task {func.__name__}: {e!s}",
                        exc_info=True,
                    )
                    raise

        return self._executor.submit(wrapper)

    def shutdown(self, wait: bool = True) -> None:
        """Shut down the underlying thread pool."""
        if self._executor:
            self._executor.shutdown(wait=wait)
