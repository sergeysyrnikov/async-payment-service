"""Domain-level exceptions."""


class DomainException(Exception):
    """Base domain exception."""

    def __init__(self, message: str, code: str | None = None):
        self.message = message
        self.code = code
        super().__init__(message)


class EntityNotFoundError(DomainException):
    """Raised when an expected entity is absent from storage (e.g. missing row after save)."""

    def __init__(self, message: str, code: str | None = None) -> None:
        self.message = message
        self.code = code
        super().__init__(message, code)


class DependencyConflictError(DomainException):
    """Raised when a delete cannot complete because dependent rows exist (e.g. FK references)."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "DEPENDENCY_CONFLICT",
        details: dict[str, int] | None = None,
    ) -> None:
        self.message = message
        self.code = code
        self.details = details
        super().__init__(message, code)


class ExternalServiceError(DomainException):
    """Raised when an external dependency call fails."""

    def __init__(self, service: str, message: str, code: str | None = None) -> None:
        self.service = service
        self.code = code or "EXTERNAL_SERVICE_ERROR"
        super().__init__(message, self.code)


class ExternalServiceValidationError(DomainException):
    """Raised when an external dependency rejects the request as invalid (HTTP 422 equivalent)."""

    def __init__(self, service: str, message: str, code: str | None = None) -> None:
        self.service = service
        self.code = code or "VALIDATION_ERROR"
        super().__init__(message, self.code)
