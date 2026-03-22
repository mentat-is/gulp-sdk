"""Unit tests for WebSocket and real-time features."""

import pytest
from gulp_sdk.websocket import WSMessage, WSMessageType, WSAuthPacket


@pytest.mark.unit
async def test_ws_message_parsing():
    """Test WebSocket message parsing."""
    payload = {
        "type": "docs_chunk",
        "req_id": "test-req",
        "timestamp_msec": 1234567890,
        "data": {"count": 10, "docs": []},
    }
    
    msg = WSMessage.from_json(payload)
    assert msg.type == WSMessageType.DOCUMENTS_CHUNK.value
    assert msg.req_id == "test-req"
    assert msg.data["count"] == 10


@pytest.mark.unit
async def test_ws_auth_packet():
    """Test WebSocket auth packet serialization."""
    auth = WSAuthPacket(
        token="test-token",
        ws_id="ws-id-123",
        req_id="auth-req",
    )
    
    data = auth.to_dict()
    assert data["token"] == "test-token"
    assert data["ws_id"] == "ws-id-123"
    assert data["req_id"] == "auth-req"


@pytest.mark.unit
async def test_gulp_client_websocket_method():
    """Test GulpClient.websocket() creates WebSocket instance."""
    from gulp_sdk import GulpClient
    
    client = GulpClient("http://localhost:8080", token="test-token")
    ws = client.websocket()
    
    assert ws.token == "test-token"
    assert "ws://" in ws.uri


@pytest.mark.unit
async def test_gulp_client_websocket_requires_token():
    """Test GulpClient.websocket() requires authentication."""
    from gulp_sdk import GulpClient
    
    client = GulpClient("http://localhost:8080")  # No token
    
    with pytest.raises(RuntimeError, match="requires authentication"):
        client.websocket()
