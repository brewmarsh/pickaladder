"""Custom exception classes for the application."""


class AppError(Exception):
    """Base application error class."""

    def __init__(self, message: str, status_code: int = 400) -> None:
        """Initialize the error."""
        super().__init__(message)
        self.status_code = status_code
        self.message = message


class ValidationError(AppError):
    """Raised when user input fails validation."""

    def __init__(self, message: str = "Validation failed.") -> None:
        """Initialize the error."""
        super().__init__(message, 400)


class DuplicateResourceError(AppError):
    """Raised when trying to create a resource that already exists."""

    def __init__(self, message: str = "Resource already exists.") -> None:
        """Initialize the error."""
        super().__init__(message, 409)


class NotFoundError(AppError):
    """Raised when a resource is not found."""

    def __init__(self, message: str = "Resource not found.") -> None:
        """Initialize the error."""
        super().__init__(message, 404)
