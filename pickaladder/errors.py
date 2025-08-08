class AppError(Exception):
    """Base application error class."""

    def __init__(self, message, status_code=400):
        super().__init__(message)
        self.status_code = status_code
        self.message = message


class ValidationError(AppError):
    """Raised when user input fails validation."""

    def __init__(self, message="Validation failed."):
        super().__init__(message, 400)


class DuplicateResourceError(AppError):
    """Raised when trying to create a resource that already exists."""

    def __init__(self, message="Resource already exists."):
        super().__init__(message, 409)


class NotFoundError(AppError):
    """Raised when a resource is not found."""

    def __init__(self, message="Resource not found."):
        super().__init__(message, 404)
