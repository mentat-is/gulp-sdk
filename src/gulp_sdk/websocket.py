"""
WebSocket integration for real-time updates.

Supports two usage modes:
1. Auto-managed: Client handles connection/subscription automatically
2. Manual: User explicitly controls subscription lifecycle
"""

import asyncio
import json
import logging
from dataclasses import dataclass
from typing import AsyncIterator, Callable, Any
from enum import Enum

import websockets
from websockets.client import WebSocketClientProtocol

from gulp_sdk.exceptions import NetworkError, AuthenticationError

logger = logging.getLogger(__name__)


def _build_invalid_status_errors() -> tuple[type[BaseException], ...]:
    """Return websocket invalid-status exception classes available in this version."""
    classes: list[type[BaseException]] = []
    for name in ("InvalidStatusException", "InvalidStatusCode", "InvalidStatus"):
        exc = getattr(websockets.exceptions, name, None)
        if isinstance(exc, type) and issubclass(exc, BaseException):
            classes.append(exc)
    return tuple(classes)


_WS_INVALID_STATUS_ERRORS = _build_invalid_status_errors()


class WSMessageType(str, Enum):
    """WebSocket message types."""

    CONNECTED = "ws_connected"
    ERROR = "ws_error"

    # Document/ingestion updates
    DOCUMENTS_CHUNK = "docs_chunk"
    INGEST_RAW_PROGRESS = "ingest_raw_progress"

    # Query results
    QUERY_DONE = "query_done"

    # Collaboration updates
    COLLAB_CREATE = "collab_create"
    COLLAB_UPDATE = "collab_update"
    COLLAB_DELETE = "collab_delete"

    # User/session updates
    USER_LOGIN = "user_login"
    USER_LOGOUT = "user_logout"

    # Statistics
    STATS_UPDATE = "stats_update"


@dataclass(frozen=True)
class WSMessage:
    """WebSocket message wrapper."""

    type: str
    req_id: str
    timestamp_msec: int
    data: dict[str, Any]

    @classmethod
    def from_json(cls, payload: dict[str, Any]) -> "WSMessage":
        """Parse WebSocket message from JSON payload."""
        message_data = payload.get("payload", payload.get("data", {}))
        return cls(
            type=str(payload.get("type", "")),
            req_id=payload.get("req_id", ""),
            timestamp_msec=payload.get("timestamp_msec", payload.get("@timestamp", 0)),
            data=message_data if isinstance(message_data, dict) else {},
        )


@dataclass(frozen=True)
class WSAuthPacket:
    """Authentication packet for WebSocket connection."""

    token: str
    ws_id: str
    req_id: str

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "token": self.token,
            "ws_id": self.ws_id,
            "req_id": self.req_id,
        }


class GulpWebSocket:
    """
    WebSocket client for Gulp real-time updates.

    Supports both manual and auto-managed connection modes.

    Attributes:
        uri: WebSocket URI (e.g., ws://localhost:8080/ws)
        token: Authentication token
        ws_id: Unique WebSocket connection ID
    """

    def __init__(self, uri: str, token: str, ws_id: str) -> None:
        """
        Initialize WebSocket client.

        Args:
            uri: WS/WSS connection URI
            token: Authentication token
            ws_id: Unique connection identifier
        """
        self.uri = uri
        self.token = token
        self.ws_id = ws_id

        # Connection state
        self._ws: WebSocketClientProtocol | None = None
        self._connected = False
        self._receive_task: asyncio.Task[None] | None = None

        # Message subscriptions
        self._subscriptions: dict[str, list[Callable[[WSMessage], Any]]] = {}
        self._message_queue: asyncio.Queue[WSMessage] = asyncio.Queue()

        self._logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    @property
    def is_connected(self) -> bool:
        """True when websocket transport is connected and receive loop active."""
        return self._connected

    async def connect(self) -> None:
        """
        Establish WebSocket connection and authenticate.

        Raises:
            AuthenticationError: If authentication fails
            NetworkError: If connection fails
        """
        try:
            self._ws = await websockets.connect(self.uri)
            self._logger.debug(f"Connected to {self.uri}")

            # Send authentication
            auth_packet = WSAuthPacket(
                token=self.token,
                ws_id=self.ws_id,
                req_id="auth-init",
            )
            await self._ws.send(json.dumps(auth_packet.to_dict()))

            # Wait until the server acknowledges the ws_id registration.
            raw_message = await asyncio.wait_for(self._ws.recv(), timeout=10.0)
            try:
                ack_data = json.loads(raw_message)
            except json.JSONDecodeError as e:
                raise AuthenticationError(
                    f"Unexpected WebSocket handshake response: {raw_message!r}"
                ) from e

            ack_message = WSMessage.from_json(ack_data)
            if ack_message.type == WSMessageType.ERROR.value:
                raise AuthenticationError(
                    f"WebSocket auth failed: {ack_message.data or ack_data}"
                )
            if ack_message.type != WSMessageType.CONNECTED.value:
                raise AuthenticationError(
                    f"Unexpected WebSocket handshake message: {ack_message.type}"
                )

            self._connected = True

            # Start background receive task
            self._receive_task = asyncio.create_task(self._receive_loop())

        except Exception as e:
            invalid_status_errors = _build_invalid_status_errors()
            if invalid_status_errors and isinstance(e, invalid_status_errors):
                raise AuthenticationError(f"WebSocket auth failed: {e}") from e
            if isinstance(e, TimeoutError):
                raise AuthenticationError(
                    "Timed out waiting for WebSocket handshake acknowledgment"
                ) from e
            if isinstance(e, (websockets.exceptions.WebSocketException, OSError)):
                raise NetworkError(f"WebSocket connection failed: {e}") from e
            raise

    async def disconnect(self) -> None:
        """Close WebSocket connection."""
        if self._receive_task:
            self._receive_task.cancel()
            try:
                await self._receive_task
            except asyncio.CancelledError:
                pass

        if self._ws:
            await self._ws.close()
            self._connected = False
            self._logger.debug("WebSocket disconnected")

    async def subscribe(
        self,
        operation_id: str | None = None,
        req_id: str | None = None,
        message_type: WSMessageType | None = None,
    ) -> None:
        """
        Subscribe to WebSocket messages.

        Args:
            operation_id: Filter by operation ID (optional)
            req_id: Filter by request ID (optional)
            message_type: Filter by message type (optional)
        """
        if not self._connected:
            await self.connect()

        # Send subscription request
        sub_data = {
            "action": "subscribe",
            "req_id": req_id,
        }
        if operation_id:
            sub_data["operation_id"] = operation_id
        if message_type:
            sub_data["message_type"] = message_type.value

        await self._ws.send(json.dumps(sub_data))
        self._logger.debug(f"Subscribed: req_id={req_id}, op_id={operation_id}")

    async def unsubscribe(self, req_id: str | None = None) -> None:
        """
        Unsubscribe from messages.

        Args:
            req_id: Request ID to unsubscribe from
        """
        if not self._connected:
            return

        unsub_data = {
            "action": "unsubscribe",
            "req_id": req_id,
        }
        await self._ws.send(json.dumps(unsub_data))
        self._logger.debug(f"Unsubscribed: req_id={req_id}")

    def on_message(
        self, message_type: WSMessageType, callback: Callable[[WSMessage], Any]
    ) -> None:
        """
        Register callback for specific message type.

        Args:
            message_type: Message type to listen for
            callback: Async or sync callback function
        """
        key = message_type.value
        if key not in self._subscriptions:
            self._subscriptions[key] = []
        self._subscriptions[key].append(callback)

    async def _receive_loop(self) -> None:
        """Background task to receive messages from WebSocket."""
        try:
            while self._connected and self._ws:
                msg_text = await self._ws.recv()
                try:
                    msg_data = json.loads(msg_text)
                    message = WSMessage.from_json(msg_data)

                    # Trigger registered callbacks
                    for callback in self._subscriptions.get(message.type, []):
                        if asyncio.iscoroutinefunction(callback):
                            await callback(message)
                        else:
                            callback(message)

                    # Queue for async iteration
                    await self._message_queue.put(message)

                except json.JSONDecodeError:
                    self._logger.warning(f"Invalid JSON message: {msg_text}")

        except websockets.exceptions.ConnectionClosed:
            self._connected = False
            self._logger.debug("WebSocket connection closed")
        except asyncio.CancelledError:
            self._connected = False
            self._logger.debug("WebSocket receive loop cancelled")

    async def __aenter__(self) -> "GulpWebSocket":
        """Async context manager entry."""
        await self.connect()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit."""
        await self.disconnect()

    def __aiter__(self) -> AsyncIterator[WSMessage]:
        """Async iteration over messages."""
        return self

    async def __anext__(self) -> WSMessage:
        """Get next message (for async iteration)."""
        if not self._connected:
            raise StopAsyncIteration
        return await self._message_queue.get()
