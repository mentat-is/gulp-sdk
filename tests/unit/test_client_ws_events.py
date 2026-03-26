"""Unit tests for client-level websocket event helpers."""

from types import SimpleNamespace

import pytest

from gulp_sdk.client import GulpClient
from gulp_sdk.websocket import WSMessageType


@pytest.mark.unit
async def test_client_register_ws_message_handler_registers_callback(monkeypatch):
    client = GulpClient("http://localhost:8080", token="tok")
    called = {"count": 0}

    def _cb(_msg):
        called["count"] += 1

    fake_ws = SimpleNamespace()
    captured = {"type": None, "callback": None}

    def _on_message(message_type, callback):
        captured["type"] = message_type
        captured["callback"] = callback

    fake_ws.on_message = _on_message

    async def _ensure_ws():
        return fake_ws

    monkeypatch.setattr(client, "ensure_websocket", _ensure_ws)

    ws = await client.register_ws_message_handler(WSMessageType.STATS_UPDATE, _cb)
    assert ws is fake_ws
    assert captured["type"] == WSMessageType.STATS_UPDATE
    assert captured["callback"] is _cb
    assert called["count"] == 0


@pytest.mark.unit
async def test_client_unregister_ws_message_handler_ignores_missing_ws():
    client = GulpClient("http://localhost:8080", token="tok")

    def _cb(_msg):
        return None

    # Should not raise when no default websocket exists.
    client.unregister_ws_message_handler(WSMessageType.STATS_UPDATE, _cb)


@pytest.mark.unit
async def test_client_unregister_ws_message_handler_unregisters_callback():
    client = GulpClient("http://localhost:8080", token="tok")

    captured = {"type": None, "callback": None}

    def _off_message(message_type, callback):
        captured["type"] = message_type
        captured["callback"] = callback

    client._ws = SimpleNamespace(off_message=_off_message)

    def _cb(_msg):
        return None

    client.unregister_ws_message_handler(WSMessageType.QUERY_DONE, _cb)

    assert captured["type"] == WSMessageType.QUERY_DONE
    assert captured["callback"] is _cb


