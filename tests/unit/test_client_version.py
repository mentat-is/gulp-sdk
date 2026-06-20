from __future__ import annotations

import pytest

from gulp_sdk.client import GulpClient
from gulp_sdk.exceptions import AuthenticationError


@pytest.mark.unit
async def test_client_version_wraps_server_version(monkeypatch) -> None:
    client = GulpClient("http://localhost:8080")
    client.token = "tok-test"

    seen = {}

    class _FakePlugins:
        async def version(self, *, req_id: str | None = None) -> str:
            seen["req_id"] = req_id
            return "gulp v1.2.3"

    monkeypatch.setattr(GulpClient, "plugins", property(lambda self: _FakePlugins()))

    assert await client.version(req_id="req-123") == "gulp v1.2.3"
    assert seen["req_id"] == "req-123"


@pytest.mark.unit
async def test_client_version_requires_token() -> None:
    client = GulpClient("http://localhost:8080")

    with pytest.raises(AuthenticationError, match="requires an authentication token"):
        await client.version()
