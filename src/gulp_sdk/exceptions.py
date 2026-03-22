"""
Exception hierarchy for the Gulp SDK.

All exceptions inherit from GulpSDKError for unified error handling.
The HTTP status code and original response data are preserved for debugging.
"""

from typing import Any


class GulpSDKError(Exception):
    """Base exception for all Gulp SDK errors."""

    def __init__(
        self,
        message: str,
        status_code: int | None = None,
        response_data: dict[str, Any] | None = None,
    ) -> None:
        """
        Initialize a Gulp SDK exception.

        Args:
            message: Human-readable error message
            status_code: HTTP status code (if applicable)
            response_data: Original response data from server
        """
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.response_data = response_data or {}


class AuthenticationError(GulpSDKError):
    """
    Raised when authentication fails (invalid token, wrong credentials).

    Typically corresponds to HTTP 401 Unauthorized.
    """

    pass


class PermissionError(GulpSDKError):
    """
    Raised when user lacks required permission for the operation.

    Typically corresponds to HTTP 403 Forbidden.
    """

    pass


class NotFoundError(GulpSDKError):
    """
    Raised when a requested resource does not exist.

    Typically corresponds to HTTP 404 Not Found.
    """

    pass


class AlreadyExistsError(GulpSDKError):
    """
    Raised when attempting to create a resource that already exists.

    Typically corresponds to HTTP 409 Conflict.
    """

    pass


class ValidationError(GulpSDKError):
    """
    Raised when request data fails validation.

    Typically corresponds to HTTP 422 Unprocessable Entity.
    """

    pass


class NetworkError(GulpSDKError):
    """Raised when a network-level error occurs (timeout, connection refused, etc.)."""

    pass


class SessionExpiredError(AuthenticationError):
    """Raised when an authenticated session has expired."""

    pass
