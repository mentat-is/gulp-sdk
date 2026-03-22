"""Advanced unit tests for GulpClient and GulpWebSocket internals."""

import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest

from gulp_sdk.client import GulpClient
from gulp_sdk.exceptions import (
    AlreadyExistsError,
    AuthenticationError,
    GulpSDKError,
    NetworkError,
    NotFoundError,
    PermissionError,
    ValidationError,
)
from gulp_sdk.websocket import GulpWebSocket, WSMessageType


class _Resp:
    def __init__(self, status_code: int, payload: dict | None = None, text: str = ""):
        self.status_code = status_code
        self._payload = payload
        self.text = text
        self.content = text.encode("utf-8") if text else b"{}"

    def json(self):
        if self._payload is None:
            raise ValueError("no json")
        return self._payload


class _RespNoJson:
    def __init__(self, status_code: int, text: str = "plain-error"):
        self.status_code = status_code
        self.text = text

    def json(self):
        raise ValueError("not json")


class _FakeWS:
    def __init__(self, recv_messages: list[str]):
        self.sent: list[str] = []
        self._recv = list(recv_messages)
        self.closed = False

    async def send(self, msg: str):
        self.sent.append(msg)

    async def recv(self):
        if self._recv:
            return self._recv.pop(0)
        # Keep the receive loop alive until the test explicitly disconnects/cancels it.
        await asyncio.Event().wait()

    async def close(self):
        self.closed = True


@pytest.mark.unit
async def test_client_raise_for_status_mapping():
    c = GulpClient("http://localhost:8080")
    data = {"data": {"msg": "x"}}

    with pytest.raises(AuthenticationError):
        c._raise_for_status(401, data)
    with pytest.raises(PermissionError):
        c._raise_for_status(403, data)
    with pytest.raises(NotFoundError):
        c._raise_for_status(404, data)
    with pytest.raises(AlreadyExistsError):
        c._raise_for_status(409, data)
    with pytest.raises(ValidationError):
        c._raise_for_status(422, data)
    with pytest.raises(GulpSDKError):
        c._raise_for_status(500, data)


@pytest.mark.unit
async def test_client_request_retry_and_network_error():
    c = GulpClient("http://localhost:8080")
    c._http_client = SimpleNamespace()
    c._retry_policy.max_retries = 1

    c._http_client.request = AsyncMock(
        side_effect=[
            httpx.NetworkError("net"),
            _Resp(200, {"status": "success", "data": {"ok": True}}),
        ]
    )

    out = await c._request("GET", "/x")
    assert out["data"]["ok"] is True


@pytest.mark.unit
async def test_client_request_http_error_no_retry():
    c = GulpClient("http://localhost:8080")
    c._http_client = SimpleNamespace()
    c._retry_policy.max_retries = 0
    c._http_client.request = AsyncMock(
        return_value=_Resp(500, {"status": "error", "data": {"err": "boom"}})
    )

    with pytest.raises(GulpSDKError):
        await c._request("GET", "/x")


@pytest.mark.unit
async def test_client_ensure_websocket_requires_token():
    c = GulpClient("http://localhost:8080")
    with pytest.raises(RuntimeError):
        await c.ensure_websocket()


@pytest.mark.unit
async def test_websocket_connect_subscribe_callbacks(monkeypatch):
    connected = json.dumps({"type": "ws_connected", "req_id": "a", "timestamp_msec": 1, "payload": {}})
    docs = json.dumps({"type": "docs_chunk", "req_id": "r1", "timestamp_msec": 2, "payload": {"docs": []}})
    bad = "not-json"
    fake_ws = _FakeWS([connected, docs, bad])

    async def _fake_connect(uri):
        return fake_ws

    monkeypatch.setattr("gulp_sdk.websocket.websockets.connect", _fake_connect)

    ws = GulpWebSocket("ws://localhost:8080/ws", "tok", "ws1")
    got = []

    def cb(msg):
        got.append(msg.type)

    ws.on_message(WSMessageType.DOCUMENTS_CHUNK, cb)
    await ws.connect()
    await ws.subscribe(operation_id="op1", req_id="r1", message_type=WSMessageType.DOCUMENTS_CHUNK)
    await asyncio.sleep(0.05)
    await ws.unsubscribe(req_id="r1")
    await ws.disconnect()

    assert ws.is_connected is False
    assert "docs_chunk" in got
    assert any("subscribe" in s for s in fake_ws.sent)
    assert any("unsubscribe" in s for s in fake_ws.sent)


@pytest.mark.unit
async def test_websocket_context_manager(monkeypatch):
    connected = json.dumps({"type": "ws_connected", "req_id": "a", "timestamp_msec": 1, "payload": {}})
    fake_ws = _FakeWS([connected])

    async def _fake_connect(uri):
        return fake_ws

    monkeypatch.setattr("gulp_sdk.websocket.websockets.connect", _fake_connect)

    async with GulpWebSocket("ws://localhost:8080/ws", "tok", "ws1") as ws:
        assert ws.is_connected


@pytest.mark.unit
async def test_websocket_handshake_error_paths(monkeypatch):
    from gulp_sdk import websocket as ws_module

    if not hasattr(ws_module.websockets.exceptions, "InvalidStatusException"):
        class _CompatInvalidStatus(RuntimeError):
            pass

        monkeypatch.setattr(ws_module.websockets.exceptions, "InvalidStatusException", _CompatInvalidStatus, raising=False)

    async def _fake_connect_bad_json(uri):
        return _FakeWS(["not-json"])

    monkeypatch.setattr("gulp_sdk.websocket.websockets.connect", _fake_connect_bad_json)
    ws = GulpWebSocket("ws://localhost:8080/ws", "tok", "ws1")
    with pytest.raises(AuthenticationError):
        await ws.connect()

    async def _fake_connect_ws_error(uri):
        err = json.dumps({"type": "ws_error", "req_id": "a", "timestamp_msec": 1, "payload": {"msg": "x"}})
        return _FakeWS([err])

    monkeypatch.setattr("gulp_sdk.websocket.websockets.connect", _fake_connect_ws_error)
    ws = GulpWebSocket("ws://localhost:8080/ws", "tok", "ws1")
    with pytest.raises(AuthenticationError):
        await ws.connect()

    async def _fake_connect_unexpected(uri):
        msg = json.dumps({"type": "other", "req_id": "a", "timestamp_msec": 1, "payload": {}})
        return _FakeWS([msg])

    monkeypatch.setattr("gulp_sdk.websocket.websockets.connect", _fake_connect_unexpected)
    ws = GulpWebSocket("ws://localhost:8080/ws", "tok", "ws1")
    with pytest.raises(AuthenticationError):
        await ws.connect()

    # explicit branch for InvalidStatusException handling
    class _InvalidStatus(Exception):
        pass

    monkeypatch.setattr(ws_module.websockets.exceptions, "InvalidStatusException", _InvalidStatus, raising=False)

    async def _fake_connect_invalid_status(uri):
        raise _InvalidStatus("401")

    monkeypatch.setattr("gulp_sdk.websocket.websockets.connect", _fake_connect_invalid_status)
    ws = GulpWebSocket("ws://localhost:8080/ws", "tok", "ws1")
    with pytest.raises(AuthenticationError):
        await ws.connect()


@pytest.mark.unit
async def test_websocket_connect_timeout_and_network_error(monkeypatch):
    from gulp_sdk import websocket as ws_module

    if not hasattr(ws_module.websockets.exceptions, "InvalidStatusException"):
        class _CompatInvalidStatus(RuntimeError):
            pass

        monkeypatch.setattr(ws_module.websockets.exceptions, "InvalidStatusException", _CompatInvalidStatus, raising=False)

    async def _fake_connect_timeout(uri):
        return _FakeWS([])

    async def _raise_timeout(awaitable, timeout):
        # Ensure the awaited coroutine is closed to avoid unawaited-coroutine warnings
        if hasattr(awaitable, "close"):
            awaitable.close()
        raise TimeoutError("timeout")

    monkeypatch.setattr("gulp_sdk.websocket.websockets.connect", _fake_connect_timeout)
    monkeypatch.setattr("gulp_sdk.websocket.asyncio.wait_for", _raise_timeout)

    ws = GulpWebSocket("ws://localhost:8080/ws", "tok", "ws1")
    with pytest.raises(AuthenticationError):
        await ws.connect()

    async def _raise_oserror(uri):
        raise OSError("no route")

    monkeypatch.setattr("gulp_sdk.websocket.websockets.connect", _raise_oserror)
    ws = GulpWebSocket("ws://localhost:8080/ws", "tok", "ws1")
    with pytest.raises(NetworkError):
        await ws.connect()


@pytest.mark.unit
async def test_websocket_receive_loop_async_callback_and_stop_iteration():
    ws = GulpWebSocket("ws://localhost:8080/ws", "tok", "ws1")
    ws._connected = True

    class _WS:
        def __init__(self):
            self._calls = 0

        async def recv(self):
            self._calls += 1
            if self._calls == 1:
                return json.dumps({"type": "docs_chunk", "req_id": "r1", "timestamp_msec": 1, "payload": {}})
            raise asyncio.CancelledError()

    ws._ws = _WS()
    seen = []

    async def cb(msg):
        seen.append(msg.type)

    ws.on_message(WSMessageType.DOCUMENTS_CHUNK, cb)
    await ws._receive_loop()
    assert "docs_chunk" in seen

    ws._connected = False
    with pytest.raises(StopAsyncIteration):
        await ws.__anext__()


@pytest.mark.unit
async def test_client_additional_branches_and_properties(monkeypatch):
    c = GulpClient("https://localhost:8080", token="tok")

    # Cover property access branches.
    _ = c.documents
    _ = c.acl
    _ = c.db

    # Cover _client runtime error branch.
    c._http_client = None
    with pytest.raises(RuntimeError):
        _ = c._client

    # Cover non-JSON response parsing and timeout retry exhaustion.
    c._http_client = SimpleNamespace()
    c._retry_policy.max_retries = 0
    c._http_client.request = AsyncMock(return_value=_RespNoJson(200, text="ok-text"))
    out = await c._request("GET", "/x")
    assert out["status"] == "error"

    c._http_client.request = AsyncMock(side_effect=httpx.TimeoutException("slow"))
    with pytest.raises(NetworkError):
        await c._request("GET", "/x")

    # Cover _raise_for_status fallback message branch.
    with pytest.raises(GulpSDKError):
        c._raise_for_status(500, {"data": 123})

    # Cover websocket URL conversion path with https -> wss.
    ws = c.websocket()
    assert ws.uri.startswith("wss://")
