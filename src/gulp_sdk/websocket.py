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
import contextlib

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
    INGEST_SOURCE_DONE = "ingest_source_done"
    INGEST_RAW_PROGRESS = "ingest_raw_progress"
    REBASE_DONE = "rebase_done"

    # Query results
    QUERY_GROUP_MATCH = "query_group_match"
    QUERY_DONE = "query_done"

    # Collaboration updates
    COLLAB_CREATE = "collab_create"
    COLLAB_UPDATE = "collab_update"
    COLLAB_DELETE = "collab_delete"

    # User/session updates
    USER_LOGIN = "user_login"
    USER_LOGOUT = "user_logout"

    # Statistics
    STATS_CREATE = "stats_create"
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
        self._connect_lock = asyncio.Lock()
        self._disconnect_requested = False

        # Message subscriptions
        self._subscriptions: dict[str, list[Callable[[WSMessage], Any]]] = {}
        self._server_subscriptions: list[dict[str, str]] = []
        self._callback_tasks: set[asyncio.Task[Any]] = set()
        # Bounded queue to avoid unbounded memory growth when users rely on
        # callbacks and do not consume async iteration.
        self._message_queue: asyncio.Queue[WSMessage] = asyncio.Queue(maxsize=2048)

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
        async with self._connect_lock:
            if self._connected and self._ws is not None:
                return
            self._disconnect_requested = False
            await self._open_connection_and_authenticate()
            self._connected = True

            # Start background receive task
            self._receive_task = asyncio.create_task(self._receive_loop())

    async def disconnect(self) -> None:
        """Close WebSocket connection."""
        self._disconnect_requested = True
        if self._receive_task:
            self._receive_task.cancel()
            try:
                await self._receive_task
            except asyncio.CancelledError:
                pass
            self._receive_task = None

        for task in list(self._callback_tasks):
            task.cancel()
        for task in list(self._callback_tasks):
            with contextlib.suppress(asyncio.CancelledError):
                await task
        self._callback_tasks.clear()

        if self._ws:
            await self._ws.close()
            self._ws = None

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
        self._remember_server_subscription(sub_data)

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
        self._forget_server_subscription(req_id)

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

    def off_message(
        self, message_type: WSMessageType, callback: Callable[[WSMessage], Any]
    ) -> None:
        """
        Unregister callback for specific message type.

        Args:
            message_type: Message type callback was registered for
            callback: Callback function to remove
        """
        key = message_type.value
        callbacks = self._subscriptions.get(key)
        if not callbacks:
            return
        try:
            callbacks.remove(callback)
        except ValueError:
            return
        if not callbacks:
            self._subscriptions.pop(key, None)

    async def _receive_loop(self) -> None:
        """Background task to receive messages from WebSocket."""
        try:
            while self._connected and self._ws:
                try:
                    msg_text = await self._ws.recv()
                except websockets.exceptions.ConnectionClosed as exc:
                    if self._disconnect_requested:
                        self._connected = False
                        self._logger.debug("WebSocket connection closed (requested)")
                        return

                    self._logger.warning(
                        "WebSocket connection closed unexpectedly code=%s reason=%s; reconnecting",
                        getattr(exc, "code", "unknown"),
                        getattr(exc, "reason", ""),
                    )
                    reconnected = await self._reconnect_after_close()
                    if not reconnected:
                        self._connected = False
                        self._logger.error("WebSocket reconnection failed")
                        return
                    continue
                try:
                    msg_data = json.loads(msg_text)
                    message = WSMessage.from_json(msg_data)

                    # Trigger registered callbacks (isolate callback failures so
                    # one bad handler does not terminate the receive loop).
                    for callback in self._subscriptions.get(message.type, []):
                        self._dispatch_callback(callback, message)
                    if self._subscriptions.get(message.type):
                        await asyncio.sleep(0)

                    # Queue for async iteration. If full, drop the oldest item
                    # and keep the newest so the stream remains live under load.
                    try:
                        self._message_queue.put_nowait(message)
                    except asyncio.QueueFull:
                        try:
                            self._message_queue.get_nowait()
                        except asyncio.QueueEmpty:
                            pass
                        try:
                            self._message_queue.put_nowait(message)
                        except asyncio.QueueFull:
                            pass

                except json.JSONDecodeError:
                    self._logger.warning(f"Invalid JSON message: {msg_text}")

        except asyncio.CancelledError:
            self._connected = False
            self._logger.debug("WebSocket receive loop cancelled")
        except Exception:
            self._connected = False
            self._logger.exception("WebSocket receive loop crashed")

    async def _open_connection_and_authenticate(self) -> None:
        try:
            self._ws = await self._connect_transport()
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

            await self._replay_server_subscriptions()

        except Exception as e:
            if self._ws is not None:
                with contextlib.suppress(Exception):
                    await self._ws.close()
                self._ws = None

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

    async def _connect_transport(self) -> WebSocketClientProtocol:
        connect_kwargs = {
            # Under heavy load, keepalive should not close the socket only
            # because a pong is delayed.
            "ping_interval": None,
            "ping_timeout": None,
            "close_timeout": 30,
            # Server can emit large collab/query payloads; disable frame-size
            # cap so the client does not close with 1009 (message too big).
            "max_size": None,
            # Avoid transport-level backpressure disconnects under high-volume
            # notification bursts (e.g. thousands of QUERY_DONE events).
            "max_queue": 4096,
        }
        try:
            return await websockets.connect(self.uri, **connect_kwargs)
        except TypeError:
            # Compatibility with tests/custom shims that implement
            # connect(uri) only.
            return await websockets.connect(self.uri)

    async def _reconnect_after_close(self) -> bool:
        for attempt in range(1, 4):
            if self._disconnect_requested:
                return False
            try:
                async with self._connect_lock:
                    if self._disconnect_requested:
                        return False
                    await self._open_connection_and_authenticate()
                    self._connected = True
                    self._logger.info("WebSocket reconnected (attempt %d)", attempt)
                    return True
            except Exception:
                self._logger.warning(
                    "WebSocket reconnect attempt %d failed",
                    attempt,
                    exc_info=True,
                )
                await asyncio.sleep(min(3.0, 0.5 * attempt))
        return False

    def _remember_server_subscription(self, sub_data: dict[str, Any]) -> None:
        req_id = sub_data.get("req_id")
        operation_id = sub_data.get("operation_id")
        message_type = sub_data.get("message_type")
        key = {
            "req_id": str(req_id) if req_id is not None else "",
            "operation_id": str(operation_id) if operation_id is not None else "",
            "message_type": str(message_type) if message_type is not None else "",
        }
        if key not in self._server_subscriptions:
            self._server_subscriptions.append(key)

    def _forget_server_subscription(self, req_id: str | None) -> None:
        req_key = "" if req_id is None else str(req_id)
        self._server_subscriptions = [
            sub for sub in self._server_subscriptions if sub.get("req_id", "") != req_key
        ]

    async def _replay_server_subscriptions(self) -> None:
        if self._ws is None:
            return
        for sub in self._server_subscriptions:
            payload: dict[str, Any] = {
                "action": "subscribe",
                "req_id": sub.get("req_id") or None,
            }
            operation_id = sub.get("operation_id")
            if operation_id:
                payload["operation_id"] = operation_id
            message_type = sub.get("message_type")
            if message_type:
                payload["message_type"] = message_type
            await self._ws.send(json.dumps(payload))

    def _dispatch_callback(
        self,
        callback: Callable[[WSMessage], Any],
        message: WSMessage,
    ) -> None:
        async def _run_callback() -> None:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(message)
                else:
                    await asyncio.to_thread(callback, message)
            except Exception:
                self._logger.exception(
                    "WebSocket callback failed for message type=%s",
                    message.type,
                )

        task = asyncio.create_task(_run_callback())
        self._callback_tasks.add(task)
        task.add_done_callback(self._callback_tasks.discard)

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
