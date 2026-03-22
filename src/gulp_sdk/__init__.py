"""
Gulp Python SDK — Async client for the Gulp document analysis platform.

This module provides a high-level async Python interface to all Gulp APIs:
- REST endpoints (operations, documents, queries, users, collaboration, plugins)
- WebSocket real-time updates
- Async pagination helpers
- Type-safe request/response handling

Quick start:
    ```python
    from gulp_sdk import GulpClient, AuthenticationError

    async with GulpClient("http://localhost:8080") as client:
        # Login
        token = await client.auth.login("user", "password")
        
        # Create operation
        op = await client.operations.create("My Operation", "Description")
        
        # List documents
        async for doc in client.documents.list(op.id):
            print(doc.id, doc.content[:50])
    ```
"""

from gulp_sdk.client import GulpClient
from gulp_sdk.exceptions import (
    GulpSDKError,
    AuthenticationError,
    PermissionError,
    NotFoundError,
    AlreadyExistsError,
    ValidationError,
    NetworkError,
    SessionExpiredError,
)
from gulp_sdk.models import (
    JSendResponse,
    JSendStatus,
    User,
    TokenSession,
    Operation,
    GulpDocument,
    Note,
    Link,
    Highlight,
    Glyph,
    UserGroup,
    RequestStats,
    PluginEntry,
    MappingFile,
    EnhanceDocumentMap,
)
from gulp_sdk.websocket import GulpWebSocket, WSMessage, WSMessageType
from gulp_sdk.pagination import AsyncPaginator, CursorPaginator
from gulp_sdk.utils import RequestLogger, RetryPolicy

try:
    from importlib.metadata import version, PackageNotFoundError

    __version__ = version("gulp-sdk")
except Exception:
    # During editable installs or source tree usage fallback to setuptools_scm-generated file
    try:
        from gulp_sdk._version import version as __version__
    except Exception:
        __version__ = "0.0.0"

__all__ = [
    # Client
    "GulpClient",
    # Exceptions
    "GulpSDKError",
    "AuthenticationError",
    "PermissionError",
    "NotFoundError",
    "AlreadyExistsError",
    "ValidationError",
    "NetworkError",
    "SessionExpiredError",
    # Models
    "JSendResponse",
    "JSendStatus",
    "User",
    "TokenSession",
    "Operation",
    "GulpDocument",
    "Note",
    "Link",
    "Highlight",
    "Glyph",
    "UserGroup",
    "RequestStats",
    "PluginEntry",
    "MappingFile",
    "EnhanceDocumentMap",
    # WebSocket
    "GulpWebSocket",
    "WSMessage",
    "WSMessageType",
    # Utilities
    "AsyncPaginator",
    "CursorPaginator",
    "RequestLogger",
    "RetryPolicy",
]

