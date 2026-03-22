"""
Core GulpClient — main async HTTP client for Gulp API.

Usage:
    ```python
    async with GulpClient("http://localhost:8080") as client:
        token = await client.auth.login("user", "pass")
        op = await client.operations.create("Name", "Desc")
    ```

WebSocket usage:
    ```python
    async with GulpClient("http://localhost:8080") as client:
        async with client.websocket() as ws:
            await ws.subscribe(operation_id)
            async for message in ws:
                print(f"Update: {message.type}")
    ```
"""

from typing import Any
import httpx
import inspect
import logging
import uuid
import time

from gulp_sdk.exceptions import GulpSDKError, AuthenticationError
from gulp_sdk.models import JSendResponse, TokenSession
from gulp_sdk.websocket import GulpWebSocket
from gulp_sdk.utils import RequestLogger, RetryPolicy, format_error_message

logger = logging.getLogger(__name__)


class GulpClient:
    """
    Async HTTP client for Gulp API.

    Manages HTTP session, authentication tokens, request signing, and error handling.
    Provides method groups for different API categories.

    Attributes:
        base_url: Gulp server URL (e.g., "http://localhost:8080")
        timeout: Request timeout in seconds (default: 30)
        token: Current authentication token
    """

    def __init__(
        self,
        base_url: str,
        token: str | None = None,
        timeout: float = 30.0,
        ws_auto_connect: bool = True,
    ) -> None:
        """
        Initialize GulpClient.

        Args:
            base_url: Gulp server base URL
            token: Optional authentication token
            timeout: HTTP request timeout in seconds
            ws_auto_connect: Auto-connect WebSocket on context entry
        """
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.timeout = timeout
        self.ws_auto_connect = ws_auto_connect

        # HTTP client (created in __aenter__)
        self._http_client: httpx.AsyncClient | None = None

        # WebSocket connection
        self._ws_id = str(uuid.uuid4())
        self._ws: GulpWebSocket | None = None

        # Request utilities
        self._request_logger = RequestLogger(logger)
        self._retry_policy = RetryPolicy(max_retries=3)

        # Log configuration
        self._logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    async def __aenter__(self) -> "GulpClient":
        """Async context manager entry — create HTTP session."""
        self._http_client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=self.timeout,
            follow_redirects=True,
        )
        self._logger.debug(f"Connected to {self.base_url}")
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit — close HTTP session."""
        if self._ws is not None:
            try:
                await self._ws.disconnect()
            finally:
                self._ws = None

        if self._http_client:
            await self._http_client.aclose()
            self._logger.debug("HTTP client closed")

    @property
    def ws_id(self) -> str:
        """Current websocket id used for API calls requiring websocket correlation."""
        return self._ws_id

    async def ensure_websocket(self) -> GulpWebSocket:
        """
        Ensure a default websocket is connected for the current authenticated token.

        Returns:
            Connected GulpWebSocket instance.
        """
        if not self.token:
            raise RuntimeError("Cannot connect websocket without an authentication token")

        if self._ws is not None and self._ws.is_connected:
            return self._ws

        self._ws = self.websocket()
        await self._ws.connect()
        return self._ws

    @property
    def _client(self) -> httpx.AsyncClient:
        """Get active HTTP client or raise if not in context."""
        if self._http_client is None:
            raise RuntimeError(
                "GulpClient must be used as async context manager: "
                "async with GulpClient(...) as client: ..."
            )
        return self._http_client

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        data: Any = None,
        files: Any = None,
        timeout: float | None = None,
    ) -> dict[str, Any]:
        """
        Make HTTP request with token injection, retry logic, and error handling.

        Args:
            method: HTTP method (GET, POST, etc.)
            path: API path (relative to base_url)
            json: JSON request body
            params: Query parameters
            headers: Additional headers
            data: Form data
            files: File uploads
            timeout: Request timeout override

        Returns:
            Parsed response dictionary

        Raises:
            AuthenticationError: If token is invalid or missing
            PermissionError: If user lacks required permission
            NotFoundError: If resource not found
            ValidationError: If request data is invalid
            NetworkError: If network-level error occurs
            GulpSDKError: For other errors
        """
        # Build headers
        req_headers = headers.copy() if headers else {}
        if self.token:
            req_headers["token"] = self.token

        # Attempt with retry logic
        last_error: Exception | None = None
        for attempt in range(self._retry_policy.max_retries + 1):
            try:
                # Log request
                self._request_logger.log_request(method, path, req_headers, json)
                
                start_time = time.time()
                response = await self._client.request(
                    method,
                    path,
                    json=json,
                    params=params,
                    headers=req_headers,
                    data=data,
                    files=files,
                    timeout=timeout or self.timeout,
                )
                elapsed_ms = (time.time() - start_time) * 1000

                # Parse response
                try:
                    response_data = response.json()
                except Exception:
                    response_data = {"status": "error", "data": response.text}

                # Log response
                self._request_logger.log_response(response.status_code, response_data, elapsed_ms)

                # Handle HTTP errors
                if response.status_code >= 400:
                    should_retry = self._retry_policy.should_retry(
                        response.status_code, attempt
                    )
                    if should_retry and attempt < self._retry_policy.max_retries:
                        delay = self._retry_policy.get_delay(attempt)
                        self._logger.debug(
                            f"Retrying {method} {path} after {delay:.2f}s "
                            f"(attempt {attempt + 1}/{self._retry_policy.max_retries})"
                        )
                        import asyncio
                        await asyncio.sleep(delay)
                        continue

                    maybe = self._raise_for_status(response.status_code, response_data)
                    if inspect.isawaitable(maybe):
                        await maybe

                return response_data

            except (AuthenticationError, GulpSDKError):
                raise
            except httpx.NetworkError as e:
                from gulp_sdk.exceptions import NetworkError

                self._request_logger.log_error(e, context="network")
                last_error = NetworkError(f"Network error: {e}") 
            except httpx.TimeoutException as e:
                from gulp_sdk.exceptions import NetworkError

                self._request_logger.log_error(e, context="timeout")
                last_error = NetworkError(f"Request timeout: {e}")

            # Retry on certain exceptions
            if isinstance(last_error, (NetworkError,)):
                if attempt < self._retry_policy.max_retries:
                    delay = self._retry_policy.get_delay(attempt)
                    self._logger.debug(
                        f"Retrying {method} {path} after {delay:.2f}s "
                        f"due to {type(last_error).__name__}"
                    )
                    import asyncio
                    await asyncio.sleep(delay)
                    continue

        # All retries exhausted
        if last_error:
            raise last_error

        raise GulpSDKError("Request failed after all retry attempts")

    def _raise_for_status(self, status_code: int, response_data: dict[str, Any]) -> None:
        """
        Raise appropriate exception based on status code and response.

        Args:
            status_code: HTTP status code
            response_data: Response dictionary

        Raises:
            AuthenticationError, PermissionError, NotFoundError, etc.
        """
        from gulp_sdk.exceptions import (
            PermissionError as GulpPermissionError,
            NotFoundError as GulpNotFoundError,
            AlreadyExistsError,
            ValidationError as GulpValidationError,
        )

        data_val = response_data.get("data")
        if isinstance(data_val, str):
            error_msg = data_val
        elif isinstance(data_val, dict):
            error_msg = str(data_val)
        else:
            error_msg = "Unknown error"

        if status_code == 401:
            raise AuthenticationError(error_msg, status_code, response_data)
        elif status_code == 403:
            raise GulpPermissionError(error_msg, status_code, response_data)
        elif status_code == 404:
            raise GulpNotFoundError(error_msg, status_code, response_data)
        elif status_code == 409:
            raise AlreadyExistsError(error_msg, status_code, response_data)
        elif status_code == 422:
            raise GulpValidationError(error_msg, status_code, response_data)
        else:
            raise GulpSDKError(error_msg, status_code, response_data)

    def websocket(self) -> GulpWebSocket:
        """
        Get WebSocket connection for real-time updates.

        Usage (manual mode):
            ```python
            async with client.websocket() as ws:
                await ws.subscribe(operation_id)
                async for message in ws:
                    print(message)
            ```

        Returns:
            GulpWebSocket instance in manual mode

        Raises:
            RuntimeError: If not in async context
        """
        if not self.token:
            raise RuntimeError("WebSocket requires authentication token")

        # Convert HTTP URL to WS URL
        ws_url = self.base_url.replace("http://", "ws://").replace("https://", "wss://")
        ws_uri = f"{ws_url}/ws"

        return GulpWebSocket(ws_uri, self.token, self._ws_id)

    # API endpoint groups (to be implemented in phase 4)

    @property
    def auth(self) -> "AuthAPI":
        """Authentication endpoints."""
        from gulp_sdk.api.auth import AuthAPI

        return AuthAPI(self)

    @property
    def operations(self) -> "OperationsAPI":
        """Operations endpoints."""
        from gulp_sdk.api.operations import OperationsAPI

        return OperationsAPI(self)

    @property
    def documents(self) -> "DocumentsAPI":
        """Documents/query endpoints."""
        from gulp_sdk.api.documents import DocumentsAPI

        return DocumentsAPI(self)

    @property
    def ingest(self) -> "IngestAPI":
        """Ingestion endpoints."""
        from gulp_sdk.api.ingest import IngestAPI

        return IngestAPI(self)

    @property
    def queries(self) -> "QueriesAPI":
        """Query endpoints."""
        from gulp_sdk.api.queries import QueriesAPI

        return QueriesAPI(self)

    @property
    def users(self) -> "UsersAPI":
        """Users/collaboration endpoints."""
        from gulp_sdk.api.users import UsersAPI

        return UsersAPI(self)

    @property
    def collab(self) -> "CollabAPI":
        """Collaboration (notes, links, etc.) endpoints."""
        from gulp_sdk.api.collab import CollabAPI

        return CollabAPI(self)

    @property
    def plugins(self) -> "PluginsAPI":
        """Plugins and utility endpoints."""
        from gulp_sdk.api.plugins import PluginsAPI

        return PluginsAPI(self)

    @property
    def user_groups(self) -> "UserGroupsAPI":
        """User groups endpoints."""
        from gulp_sdk.api.user_groups import UserGroupsAPI

        return UserGroupsAPI(self)

    @property
    def enrich(self) -> "EnrichAPI":
        """Document enrichment and tagging endpoints."""
        from gulp_sdk.api.enrich import EnrichAPI

        return EnrichAPI(self)

    @property
    def storage(self) -> "StorageAPI":
        """Storage (S3-compatible filestore) endpoints."""
        from gulp_sdk.api.storage import StorageAPI

        return StorageAPI(self)

    @property
    def acl(self) -> "AclAPI":
        """Object access-control endpoints."""
        from gulp_sdk.api.acl import AclAPI

        return AclAPI(self)

    @property
    def db(self) -> "DbAPI":
        """OpenSearch index management endpoints."""
        from gulp_sdk.api.db import DbAPI

        return DbAPI(self)


# Type hints for API groups (actual implementations in api/ submodules)
AuthAPI = Any
OperationsAPI = Any
DocumentsAPI = Any
IngestAPI = Any
QueriesAPI = Any
UsersAPI = Any
CollabAPI = Any
PluginsAPI = Any
