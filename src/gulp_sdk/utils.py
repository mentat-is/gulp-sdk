"""
Request/response utilities and helpers.

Includes JSend parsing, request logging, and retry logic.
"""

import logging
from typing import Any
from textwrap import dedent

logger = logging.getLogger(__name__)


class RequestLogger:
    """Structured logging for HTTP requests and responses."""

    def __init__(self, logger_obj: logging.Logger | None = None) -> None:
        """Initialize with optional logger."""
        self.logger = logger_obj or logging.getLogger(__name__)

    def log_request(
        self,
        method: str,
        path: str,
        headers: dict[str, str] | None = None,
        json_body: dict[str, Any] | None = None,
    ) -> None:
        """Log outgoing request."""
        # Mask sensitive headers
        safe_headers = self._mask_headers(headers or {})
        
        self.logger.debug(
            f"HTTP {method} {path}",
            extra={
                "headers": safe_headers,
                "has_body": json_body is not None,
            },
        )

    def log_response(
        self,
        status_code: int,
        response_data: dict[str, Any] | None = None,
        elapsed_ms: float = 0,
    ) -> None:
        """Log incoming response."""
        status_text = "OK" if status_code < 400 else "ERROR"
        
        self.logger.debug(
            f"HTTP {status_code} {status_text} (+{elapsed_ms:.0f}ms)",
            extra={
                "status": status_code,
                "has_data": response_data is not None,
            },
        )

    def log_error(
        self,
        error: Exception,
        status_code: int | None = None,
        context: str = "",
    ) -> None:
        """Log API error."""
        self.logger.error(
            f"API error: {error}",
            extra={
                "status": status_code,
                "context": context,
            },
            exc_info=True,
        )

    @staticmethod
    def _mask_headers(headers: dict[str, str]) -> dict[str, str]:
        """Mask sensitive headers like Authorization."""
        sensitive_keys = {"authorization", "x-api-key", "token"}
        masked = {}
        
        for key, value in headers.items():
            if key.lower() in sensitive_keys:
                masked[key] = "***MASKED***"
            else:
                masked[key] = value
        
        return masked


def format_error_message(
    message: str,
    status_code: int | None = None,
    response_data: dict[str, Any] | None = None,
) -> str:
    """Format comprehensive error message with context."""
    error_parts = [message]
    
    if status_code:
        error_parts.append(f"(HTTP {status_code})")
    
    if response_data:
        data_msg = response_data.get("data")
        if isinstance(data_msg, str):
            error_parts.append(f": {data_msg}")
    
    return " ".join(error_parts)


class RetryPolicy:
    """
    Retry strategy for failed requests.
    
    Implements exponential backoff with jitter.
    """

    def __init__(
        self,
        max_retries: int = 3,
        initial_delay: float = 0.5,
        max_delay: float = 30.0,
        backoff_factor: float = 2.0,
    ) -> None:
        """
        Initialize retry policy.

        Args:
            max_retries: Maximum number of retry attempts
            initial_delay: Initial delay in seconds
            max_delay: Maximum delay in seconds
            backoff_factor: Exponential backoff multiplier
        """
        self.max_retries = max_retries
        self.initial_delay = initial_delay
        self.max_delay = max_delay
        self.backoff_factor = backoff_factor

    def get_delay(self, attempt: int) -> float:
        """Get delay for retry attempt."""
        import random
        
        delay = min(
            self.initial_delay * (self.backoff_factor ** attempt),
            self.max_delay,
        )
        # Add jitter (±10%)
        jitter = delay * 0.1 * random.uniform(-1, 1)
        return max(0, delay + jitter)

    def should_retry(self, status_code: int, attempt: int) -> bool:
        """Determine if should retry based on status code and attempt count."""
        if attempt >= self.max_retries:
            return False

        # Retry on server errors (5xx) and specific client errors
        retryable_statuses = {408, 429, 500, 502, 503, 504}
        return status_code in retryable_statuses
