"""Unit tests for WebSocket and real-time features."""

import pytest
from gulp_sdk.websocket import (
    WS_CAPABILITY_DOCUMENTS_CHUNK_ACK,
    WSAuthPacket,
    WSDocumentsChunkAckPacket,
    WSMessage,
    WSMessageType,
)


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
async def test_ws_auth_packet_includes_filters():
    """Test WebSocket auth packet includes server-side filters."""
    auth = WSAuthPacket(
        token="test-token",
        ws_id="ws-id-123",
        req_id="auth-req",
        operation_ids=["op-a"],
        types=["stats_update", "collab_create"],
    )

    data = auth.to_dict()

    assert data["operation_ids"] == ["op-a"]
    assert data["types"] == ["stats_update", "collab_create"]


@pytest.mark.unit
async def test_documents_chunk_ack_packet_serialization():
    packet = WSDocumentsChunkAckPacket(req_id="request-1", chunk_number=7)

    assert packet.to_dict() == {
        "type": WSMessageType.DOCUMENTS_CHUNK_ACK.value,
        "req_id": "request-1",
        "payload": {"req_id": "request-1", "chunk_number": 7},
    }
    assert WS_CAPABILITY_DOCUMENTS_CHUNK_ACK == "docs_chunk_ack_v1"

    with pytest.raises(ValueError):
        WSDocumentsChunkAckPacket(req_id="request-1", chunk_number=0).to_dict()


@pytest.mark.unit
async def test_gulp_client_websocket_method():
    """Test GulpClient.websocket() creates WebSocket instance."""
    from gulp_sdk import GulpClient
    
    client = GulpClient("http://localhost:8080", token="test-token")
    ws = client.websocket()
    
    assert ws.token == "test-token"
    assert "ws://" in ws.uri


@pytest.mark.unit
async def test_gulp_client_websocket_passes_filters():
    """Test GulpClient.websocket() passes auth-time filters."""
    from gulp_sdk import GulpClient

    client = GulpClient(
        "http://localhost:8080",
        token="test-token",
        ws_operation_ids=["op-a"],
        ws_message_types=[WSMessageType.STATS_UPDATE, "collab_create"],
    )
    ws = client.websocket()

    assert ws.operation_ids == ["op-a"]
    assert ws.message_types == ["stats_update", "collab_create"]


@pytest.mark.unit
async def test_gulp_client_websocket_requires_token():
    """Test GulpClient.websocket() requires authentication."""
    from gulp_sdk import GulpClient
    
    client = GulpClient("http://localhost:8080")  # No token
    
    with pytest.raises(RuntimeError, match="requires authentication"):
        client.websocket()
