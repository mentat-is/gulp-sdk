"""Unit tests for websocket-aware request wait utilities."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from gulp_sdk.api.request_utils import wait_for_request_stats
from gulp_sdk.websocket import WSMessage, WSMessageType


class _FakeWS:
    def __init__(self) -> None:
        self._subscriptions: dict[str, list] = {}

    def on_message(self, message_type: WSMessageType, callback) -> None:
        key = message_type.value
        self._subscriptions.setdefault(key, []).append(callback)

    def off_message(self, message_type: WSMessageType, callback) -> None:
        key = message_type.value
        callbacks = self._subscriptions.get(key, [])
        if callback in callbacks:
            callbacks.remove(callback)
        if not callbacks and key in self._subscriptions:
            self._subscriptions.pop(key)

    async def emit(self, message_type: WSMessageType, req_id: str, data: dict) -> None:
        msg = WSMessage(
            type=message_type.value,
            req_id=req_id,
            timestamp_msec=1,
            data=data,
        )
        for callback in list(self._subscriptions.get(message_type.value, [])):
            callback(msg)


@pytest.mark.unit
async def test_wait_for_request_stats_uses_ws_terminal_event():
    ws = _FakeWS()
    plugins = SimpleNamespace(request_get=AsyncMock(return_value={"status": "ongoing"}))

    async def _ensure_websocket():
        return ws

    client = SimpleNamespace(plugins=plugins, ensure_websocket=_ensure_websocket)

    wait_task = asyncio.create_task(wait_for_request_stats(client, "req-1", timeout=5))
    await asyncio.sleep(0.05)
    await ws.emit(
        WSMessageType.STATS_UPDATE,
        req_id="req-1",
        data={"status": "done", "total_hits": 7},
    )

    out = await wait_task
    assert out["status"] == "done"
    assert out["total_hits"] == 7
    assert plugins.request_get.await_count == 0
    assert ws._subscriptions == {}


@pytest.mark.unit
async def test_wait_for_request_stats_ws_error_marks_failed():
    ws = _FakeWS()
    plugins = SimpleNamespace(request_get=AsyncMock(return_value={"status": "ongoing"}))

    async def _ensure_websocket():
        return ws

    client = SimpleNamespace(plugins=plugins, ensure_websocket=_ensure_websocket)

    wait_task = asyncio.create_task(wait_for_request_stats(client, "req-err", timeout=5))
    await asyncio.sleep(0.05)
    await ws.emit(
        WSMessageType.ERROR,
        req_id="req-err",
        data={"message": "boom"},
    )

    out = await wait_task
    assert out["status"] == "failed"
    assert out["req_id"] == "req-err"
    assert plugins.request_get.await_count == 0


@pytest.mark.unit
async def test_wait_for_request_stats_reads_status_from_payload_obj():
    ws = _FakeWS()
    plugins = SimpleNamespace(request_get=AsyncMock(return_value={"status": "ongoing"}))

    async def _ensure_websocket():
        return ws

    client = SimpleNamespace(plugins=plugins, ensure_websocket=_ensure_websocket)

    wait_task = asyncio.create_task(wait_for_request_stats(client, "req-obj", timeout=5))
    await asyncio.sleep(0.05)
    await ws.emit(
        WSMessageType.STATS_UPDATE,
        req_id="req-obj",
        data={"obj": {"status": "done", "processed": 11}},
    )

    out = await wait_task
    assert out["status"] == "done"
    assert out["processed"] == 11
    assert plugins.request_get.await_count == 0


@pytest.mark.unit
async def test_wait_for_request_stats_falls_back_to_polling_when_ws_unavailable():
    plugins = SimpleNamespace(request_get=AsyncMock(return_value={"status": "done", "req_id": "req-2"}))

    async def _ensure_websocket():
        raise RuntimeError("ws unavailable")

    client = SimpleNamespace(plugins=plugins, ensure_websocket=_ensure_websocket)

    out = await wait_for_request_stats(client, "req-2", timeout=5)

    assert out["status"] == "done"
    assert plugins.request_get.await_count == 1


@pytest.mark.unit
async def test_query_done_does_not_resolve_future():
    """QUERY_DONE must NOT terminate the wait — only STATS_UPDATE/ERROR should."""
    ws = _FakeWS()
    plugins = SimpleNamespace(request_get=AsyncMock(return_value={"status": "ongoing"}))

    async def _ensure_websocket():
        return ws

    client = SimpleNamespace(plugins=plugins, ensure_websocket=_ensure_websocket)

    wait_task = asyncio.create_task(wait_for_request_stats(client, "req-qd", timeout=5))
    await asyncio.sleep(0.05)
    # Emit a QUERY_DONE (progress event) — should NOT resolve the future
    await ws.emit(WSMessageType.QUERY_DONE, req_id="req-qd", data={"status": "done"})
    await asyncio.sleep(0.05)
    assert not wait_task.done(), "QUERY_DONE should not resolve the wait future"

    # Now emit the real terminal event
    await ws.emit(
        WSMessageType.STATS_UPDATE,
        req_id="req-qd",
        data={"status": "done", "completed_queries": 14},
    )
    out = await wait_task
    assert out["status"] == "done"
    assert out["completed_queries"] == 14


@pytest.mark.unit
async def test_ws_callback_receives_progress_and_terminal_events():
    """ws_callback should be called for both progress and terminal WS messages."""
    ws = _FakeWS()
    plugins = SimpleNamespace(request_get=AsyncMock(return_value={"status": "ongoing"}))

    async def _ensure_websocket():
        return ws

    client = SimpleNamespace(plugins=plugins, ensure_websocket=_ensure_websocket)

    received: list[WSMessage] = []

    def my_callback(msg: WSMessage) -> None:
        received.append(msg)

    wait_task = asyncio.create_task(
        wait_for_request_stats(client, "req-cb", timeout=5, ws_callback=my_callback)
    )
    await asyncio.sleep(0.05)

    # Emit progress event (QUERY_DONE) — callback should be called, future not resolved
    await ws.emit(WSMessageType.QUERY_DONE, req_id="req-cb", data={"q_name": "rule1", "total_hits": 3})
    await asyncio.sleep(0.05)
    assert len(received) == 1, "callback should receive QUERY_DONE progress event"
    assert received[0].type == WSMessageType.QUERY_DONE.value
    assert not wait_task.done()

    # Emit terminal event (STATS_UPDATE) — callback should be called, future resolves
    await ws.emit(
        WSMessageType.STATS_UPDATE,
        req_id="req-cb",
        data={"status": "done", "completed_queries": 1},
    )
    out = await wait_task
    assert len(received) == 2, "callback should also receive STATS_UPDATE terminal event"
    assert received[1].type == WSMessageType.STATS_UPDATE.value
    assert out["status"] == "done"
    assert out["completed_queries"] == 1


@pytest.mark.unit
async def test_ws_callback_not_called_for_other_request_ids():
    """ws_callback must only be called for messages matching the target req_id."""
    ws = _FakeWS()
    plugins = SimpleNamespace(request_get=AsyncMock(return_value={"status": "ongoing"}))

    async def _ensure_websocket():
        return ws

    client = SimpleNamespace(plugins=plugins, ensure_websocket=_ensure_websocket)

    received: list[WSMessage] = []

    wait_task = asyncio.create_task(
        wait_for_request_stats(client, "req-target", timeout=5, ws_callback=received.append)
    )
    await asyncio.sleep(0.05)

    # Message for a different req_id — must not reach callback
    await ws.emit(WSMessageType.QUERY_DONE, req_id="req-other", data={"q_name": "x"})
    await asyncio.sleep(0.05)
    assert len(received) == 0, "callback must not be called for foreign req_id"

    # Terminal message for target — resolves
    await ws.emit(
        WSMessageType.STATS_UPDATE,
        req_id="req-target",
        data={"status": "done"},
    )
    await wait_task
