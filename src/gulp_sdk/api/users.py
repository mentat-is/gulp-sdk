"""
Users API — user management, permissions, sessions.

Covers full user lifecycle: create, update, delete, list, get, session keepalive,
and per-user data storage.

Quick example::

    async with GulpClient("http://localhost:8080") as client:
        await client.auth.login("admin", "admin")

        # Create a new user
        user = await client.users.create(
            user_id="alice",
            password="Alice@1234",
            permission=["read", "edit"],
        )

        # Collect user info
        me = await client.users.me()

        # Keep session alive
        new_expiry = await client.users.session_keepalive()
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
if TYPE_CHECKING:
    from gulp_sdk.client import GulpClient


class UsersAPI:
    """
    User management endpoints.

    Most write operations require **admin** permission.
    """

    def __init__(self, client: "GulpClient") -> None:
        self.client = client

    async def me(self) -> dict[str, Any]:
        """
        Get the currently authenticated user.

        Returns:
            User dict for the current token holder.

        Raises:
            AuthenticationError: If not authenticated.
        """
        response_data = await self.client._request("GET", "/user_get_by_id")
        return response_data.get("data", {})

    # kept for backwards compat
    async def get_current(self) -> dict[str, Any]:
        """Alias for :meth:`me`."""
        return await self.me()

    async def get(
        self,
        user_id: str,
        *,
        req_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Get a user by ID (admin required for other users).

        Args:
            user_id: User ID to retrieve.
            req_id: Optional request ID.

        Returns:
            User dict.
        """
        params: dict[str, Any] = {"user_id": user_id}
        if req_id is not None:
            params["req_id"] = req_id
        response_data = await self.client._request("GET", "/user_get_by_id", params=params)
        return response_data.get("data", {})

    async def create(
        self,
        user_id: str,
        password: str,
        permission: list[str],
        *,
        email: str | None = None,
        user_data: dict[str, Any] | None = None,
        glyph_id: str | None = None,
        req_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Create a new user (admin required).

        Args:
            user_id: New user's login ID.
            password: Password (must meet complexity requirements unless
                ``debug_allow_insecure_passwords`` is enabled server-side).
            permission: List of permission strings, e.g.
                ``["read", "edit", "ingest"]``.
            email: Optional email address.
            user_data: Optional arbitrary user data dict.
            glyph_id: Optional glyph ID for user avatar.
            req_id: Optional request ID.

        Returns:
            Created user dict.
        """
        params: dict[str, Any] = {
            "user_id": user_id,
            "password": password,
        }
        if email is not None:
            params["email"] = email
        if glyph_id is not None:
            params["glyph_id"] = glyph_id
        if req_id is not None:
            params["req_id"] = req_id

        body: dict[str, Any] = {"permission": permission}
        if user_data is not None:
            body["user_data"] = user_data

        response_data = await self.client._request(
            "POST", "/user_create", json=body, params=params
        )
        return response_data.get("data", {})

    async def delete(
        self,
        user_id: str,
        *,
        req_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Delete a user (admin required). ``admin`` and ``guest`` cannot be deleted.

        Args:
            user_id: User ID to delete.
            req_id: Optional request ID.

        Returns:
            ``{"id": user_id}`` on success.
        """
        params: dict[str, Any] = {"user_id": user_id}
        if req_id is not None:
            params["req_id"] = req_id
        response_data = await self.client._request("DELETE", "/user_delete", params=params)
        return response_data.get("data", {})

    async def update(
        self,
        *,
        user_id: str | None = None,
        password: str | None = None,
        permission: list[str] | None = None,
        email: str | None = None,
        user_data: dict[str, Any] | None = None,
        merge_user_data: bool = True,
        glyph_id: str | None = None,
        req_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Update a user's attributes.

        Admin required when changing another user's attributes or permission.
        At least one of ``password``, ``permission``, ``email``, ``user_data``,
        or ``glyph_id`` must be provided.

        Args:
            user_id: User to update (omit to update self).
            password: New password.
            permission: New permission list.
            email: New email.
            user_data: User data to set/merge.
            merge_user_data: If True (default) merge with existing user data.
            glyph_id: New glyph ID.
            req_id: Optional request ID.

        Returns:
            Updated user dict.
        """
        params: dict[str, Any] = {"merge_user_data": merge_user_data}
        if user_id is not None:
            params["user_id"] = user_id
        if password is not None:
            params["password"] = password
        if email is not None:
            params["email"] = email
        if glyph_id is not None:
            params["glyph_id"] = glyph_id
        if req_id is not None:
            params["req_id"] = req_id

        body: dict[str, Any] = {}
        if permission is not None:
            body["permission"] = permission
        if user_data is not None:
            body["user_data"] = user_data

        response_data = await self.client._request(
            "PATCH", "/user_update", json=body or None, params=params
        )
        return response_data.get("data", {})

    async def list(
        self,
        *,
        req_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        List all users (admin required).

        Args:
            req_id: Optional request ID.

        Returns:
            List of user dicts.
        """
        params: dict[str, Any] = {}
        if req_id is not None:
            params["req_id"] = req_id
        response_data = await self.client._request(
            "GET", "/user_list", params=params or None
        )
        return response_data.get("data", [])

    async def session_keepalive(
        self,
        *,
        req_id: str | None = None,
    ) -> int:
        """
        Refresh the current session's expiration time.

        Returns:
            New expiration time in milliseconds since epoch.
        """
        params: dict[str, Any] = {}
        if req_id is not None:
            params["req_id"] = req_id
        response_data = await self.client._request(
            "GET", "/user_session_keepalive", params=params or None
        )
        return response_data.get("data", 0)

    async def session_list(
        self,
        *,
        user_id: str | None = None,
        req_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        List user sessions.

        Args:
            user_id: Optional user filter. Non-admin users can only query themselves.
            req_id: Optional request ID.

        Returns:
            List of session dicts.
        """
        params: dict[str, Any] = {}
        if user_id is not None:
            params["user_id"] = user_id
        if req_id is not None:
            params["req_id"] = req_id
        response_data = await self.client._request(
            "GET", "/user_session_list", params=params or None
        )
        return response_data.get("data", [])

    async def session_delete(
        self,
        session_id: str,
        *,
        req_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Delete one user session.

        Args:
            session_id: Session ID / token ID to delete.
            req_id: Optional request ID.

        Returns:
            ``{"id": session_id}`` on success.
        """
        params: dict[str, Any] = {"obj_id": session_id}
        if req_id is not None:
            params["req_id"] = req_id
        response_data = await self.client._request(
            "DELETE", "/user_session_delete", params=params
        )
        return response_data.get("data", {})

    async def set_data(
        self,
        key: str,
        value: Any,
        *,
        user_id: str | None = None,
        req_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Store a key/value pair in a user's private data.

        Args:
            key: Data key.
            value: Data value (any JSON-serializable type).
            user_id: User to set data for (omit for self).
            req_id: Optional request ID.

        Returns:
            ``{key: value}`` on success.
        """
        params: dict[str, Any] = {"key": key}
        if user_id is not None:
            params["user_id"] = user_id
        if req_id is not None:
            params["req_id"] = req_id
        response_data = await self.client._request(
            "PATCH", "/user_set_data", json=value, params=params
        )
        return response_data.get("data", {})

    async def get_data(
        self,
        key: str,
        *,
        user_id: str | None = None,
        req_id: str | None = None,
    ) -> Any:
        """
        Retrieve a value from a user's private data.

        Args:
            key: Data key.
            user_id: User to get data from (omit for self).
            req_id: Optional request ID.

        Returns:
            The stored value.
        """
        params: dict[str, Any] = {"key": key}
        if user_id is not None:
            params["user_id"] = user_id
        if req_id is not None:
            params["req_id"] = req_id
        response_data = await self.client._request(
            "GET", "/user_get_data", params=params
        )
        return response_data.get("data")

    async def delete_data(
        self,
        key: str,
        *,
        user_id: str | None = None,
        req_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Delete a key from a user's private data.

        Args:
            key: Data key.
            user_id: User to delete data from (omit for self).
            req_id: Optional request ID.

        Returns:
            Confirmation dict.
        """
        params: dict[str, Any] = {"key": key}
        if user_id is not None:
            params["user_id"] = user_id
        if req_id is not None:
            params["req_id"] = req_id
        response_data = await self.client._request(
            "DELETE", "/user_delete_data", params=params
        )
        return response_data.get("data", {})

