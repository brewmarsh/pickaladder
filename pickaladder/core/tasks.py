"""Background task execution module."""

import logging
from concurrent.futures import ThreadPoolExecutor, Future
from typing import Any, Callable, TypeVar

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
            max_workers=max_workers, thread_name_prefix="task_executor"
        )
        app.extensions["task_executor"] = self
        app.logger.info(f"Initialized TaskExecutor with {max_workers} workers")

    def run_async(self, func: Callable[..., T], *args: Any, **kwargs: Any) -> Future[T]:
        """
        Run a function asynchronously in a background thread.
        
        Ensures the Flask application context is available during execution.
        """
        if self._executor is None or self.app is None:
            raise RuntimeError("TaskExecutor not initialized with a Flask app")

        def wrapper() -> T:
            assert self.app is not None
            with self.app.app_context():
                try:
                    self.app.logger.debug(f"Starting background task: {func.__name__}")
                    result = func(*args, **kwargs)
                    self.app.logger.debug(f"Completed background task: {func.__name__}")
                    return result
                except Exception as e:
                    self.app.logger.error(
                        f"Error in background task {func.__name__}: {str(e)}",
                        exc_info=True
                    )
                    raise

        return self._executor.submit(wrapper)

    def shutdown(self, wait: bool = True) -> None:
        """Shut down the underlying thread pool."""
        if self._executor:
            self._executor.shutdown(wait=wait)
