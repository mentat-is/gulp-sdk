"""
Authentication API — login, logout, token management.
"""

import logging
from typing import TYPE_CHECKING, Any

from gulp_sdk.exceptions import AuthenticationError, NetworkError

from gulp_sdk.models import TokenSession

if TYPE_CHECKING:
    from gulp_sdk.client import GulpClient


logger = logging.getLogger(__name__)


class AuthAPI:
    """Authentication endpoints."""

    def __init__(self, client: "GulpClient") -> None:
        """Initialize with client reference."""
        self.client = client
        self._last_user_id: str | None = None

    async def login(self, user_id: str, password: str) -> TokenSession:
        """
        Authenticate with username/password, get session token.

        Args:
            user_id: Login user id
            password: Login password

        Returns:
            TokenSession with authentication token

        Raises:
            AuthenticationError: If credentials invalid
        """
        response_data = await self.client._request(
            "POST",
            "/login",
            json={"user_id": user_id, "password": password},
        )
        token_data = response_data.get("data", {})
        token_session = TokenSession.model_validate(
            {
                "token": token_data.get("token", ""),
                "user_id": token_data.get("id", ""),
                "expires_at": token_data.get("time_expire"),
            }
        )
        self.client.token = token_session.token
        self._last_user_id = token_session.user_id

        # Best effort: websocket auth can race with token propagation under
        # high concurrency. API calls continue to work without immediate WS.
        try:
            await self.client.ensure_websocket()
        except (AuthenticationError, NetworkError) as exc:
            logger.debug("Deferred websocket setup after login: %s", exc)
        return token_session

    async def logout(self) -> bool:
        """
        Logout current session, invalidate token.

        Returns:
            True if successful
        """
        await self.client._request("POST", "/logout", params={"ws_id": self.client.ws_id})

        if self.client._ws is not None:
            await self.client._ws.disconnect()
            self.client._ws = None

        self.client.token = None
        self._last_user_id = None
        return True

    async def get_available_login_api(self) -> list[dict[str, Any]]:
        """
        Get the list of available login methods.

        Does not require authentication.  Installed extension plugins may
        add additional login methods beyond the built-in ``gulp`` method.

        Returns:
            List of ``GulpLoginMethod`` dicts, each with ``name`` and
            ``endpoint`` keys.
        """
        response_data = await self.client._request(
            "GET", "/get_available_login_api"
        )
        return response_data.get("data", [])
