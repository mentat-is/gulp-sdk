"""Unit tests — no external dependencies required."""

import pytest


@pytest.mark.unit
async def test_jsend_response_parsing(jsend_success_response):
    """Test JSendResponse parses correctly."""
    from gulp_sdk.models import JSendResponse
    
    response = JSendResponse.from_dict(jsend_success_response)
    assert response.status.value == "success"
    assert response.req_id == "test-req-id"
    assert response.timestamp_msec == 1234567890


@pytest.mark.unit
async def test_exception_hierarchy():
    """Test exception inheritance chain."""
    from gulp_sdk.exceptions import (
        GulpSDKError,
        AuthenticationError,
        PermissionError,
        NotFoundError,
    )
    
    # All exceptions inherit from GulpSDKError
    assert issubclass(AuthenticationError, GulpSDKError)
    assert issubclass(PermissionError, GulpSDKError)
    assert issubclass(NotFoundError, GulpSDKError)


@pytest.mark.unit
async def test_gulp_client_init():
    """Test GulpClient initialization."""
    from gulp_sdk import GulpClient
    
    client = GulpClient("http://localhost:8080")
    assert client.base_url == "http://localhost:8080"
    assert client.timeout == 30.0
    assert client.token is None


@pytest.mark.unit
async def test_gulp_client_context_manager():
    """Test GulpClient context manager creates HTTP client."""
    from gulp_sdk import GulpClient
    
    async with GulpClient("http://localhost:8080") as client:
        # Should have http client
        assert client._http_client is not None
