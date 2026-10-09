"""Password handling in the SDK: body, not URL; the password-change step of a login."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from gulp_sdk import GulpClient
from gulp_sdk.api.auth import AuthAPI
from gulp_sdk.api.users import UsersAPI
from gulp_sdk.exceptions import (
    PasswordChangeRequiredError,
    PermissionError as GulpPermissionError,
)


@pytest.fixture
def client():
    fake = SimpleNamespace(ws_id="ws-test", token=None)
    fake._request = AsyncMock(
        return_value={"status": "success", "data": {"token": "t", "id": "alice"}}
    )
    fake.ensure_websocket = AsyncMock()
    return fake


@pytest.mark.unit
async def test_login_sends_the_new_password_only_when_given(client):
    auth = AuthAPI(client)

    await auth.login("alice", "First-Passw0rd!")
    assert client._request.await_args.kwargs["json"] == {
        "user_id": "alice",
        "password": "First-Passw0rd!",
    }

    await auth.login("alice", "First-Passw0rd!", new_password="Second-Passw0rd!")
    call = client._request.await_args
    assert call.kwargs["json"]["new_password"] == "Second-Passw0rd!"
    # nothing of it in the URL
    assert call.kwargs["params"] == {"force": True}


@pytest.mark.unit
async def test_user_passwords_travel_in_the_body_with_the_must_change_choice(client):
    users = UsersAPI(client)

    await users.create("bob", "First-Passw0rd!", ["read"])
    call = client._request.await_args
    assert call.kwargs["json"]["password"] == "First-Passw0rd!"
    assert call.kwargs["params"] == {"user_id": "bob", "must_change_password": True}

    await users.create("svc", "First-Passw0rd!", ["ingest"], must_change_password=False)
    assert client._request.await_args.kwargs["params"]["must_change_password"] is False

    await users.update(user_id="bob", password="Second-Passw0rd!")
    call = client._request.await_args
    assert call.kwargs["json"] == {"password": "Second-Passw0rd!"}
    # left to the server: true for someone else's password, false for one's own
    assert "must_change_password" not in call.kwargs["params"]
    assert "password" not in call.kwargs["params"]

    await users.update(user_id="bob", password="Second-Passw0rd!", must_change_password=False)
    assert client._request.await_args.kwargs["params"]["must_change_password"] is False


@pytest.mark.unit
def test_password_change_required_is_told_apart_from_a_missing_permission():
    client = GulpClient("http://localhost:8080")

    with pytest.raises(PasswordChangeRequiredError) as raised:
        client._raise_for_status(
            403,
            {"status": "error", "data": {"__error": {"name": "PasswordChangeRequired", "msg": "choose"}}},
        )
    # still a 403: code that only knows PermissionError keeps working
    assert isinstance(raised.value, GulpPermissionError)

    with pytest.raises(GulpPermissionError) as other:
        client._raise_for_status(
            403, {"status": "error", "data": {"__error": {"name": "MissingPermission", "msg": "no"}}}
        )
    assert not isinstance(other.value, PasswordChangeRequiredError)
