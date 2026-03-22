"""
User Groups API — create, update, delete, list groups and manage membership.

All endpoints require **admin** permission.

Quick example::

    async with GulpClient("http://localhost:8080") as client:
        await client.auth.login("admin", "admin")

        group = await client.user_groups.create(
            name="analysts",
            permission=["read", "edit"],
        )

        await client.user_groups.add_user(group["id"], "alice")
        await client.user_groups.remove_user(group["id"], "bob")

        await client.user_groups.delete(group["id"])
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from gulp_sdk.client import GulpClient


class UserGroupsAPI:
    """
    User group management endpoints.

    All operations require **admin** permission.
    """

    def __init__(self, client: "GulpClient") -> None:
        self.client = client

    async def create(
        self,
        name: str,
        permission: list[str],
        *,
        description: str | None = None,
        glyph_id: str | None = None,
        req_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Create a user group.

        Args:
            name: Group name.
            permission: List of permission strings.
            description: Optional description.
            glyph_id: Optional glyph ID.
            req_id: Optional request ID.

        Returns:
            Created group dict.
        """
        params: dict[str, Any] = {"name": name}
        if glyph_id is not None:
            params["glyph_id"] = glyph_id
        if req_id is not None:
            params["req_id"] = req_id
        body: dict[str, Any] = {"permission": permission}
        if description is not None:
            body["description"] = description
        response_data = await self.client._request(
            "POST", "/user_group_create", json=body, params=params
        )
        return response_data.get("data", {})

    async def update(
        self,
        group_id: str,
        *,
        permission: list[str] | None = None,
        description: str | None = None,
        glyph_id: str | None = None,
        req_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Update a user group (admin required).

        Args:
            group_id: Group ID.
            permission: New permission list.
            description: New description.
            glyph_id: New glyph ID.
            req_id: Optional request ID.

        Returns:
            Updated group dict.
        """
        params: dict[str, Any] = {"group_id": group_id}
        if glyph_id is not None:
            params["glyph_id"] = glyph_id
        if req_id is not None:
            params["req_id"] = req_id
        body: dict[str, Any] = {}
        if permission is not None:
            body["permission"] = permission
        if description is not None:
            body["description"] = description
        response_data = await self.client._request(
            "PATCH", "/user_group_update", json=body or None, params=params
        )
        return response_data.get("data", {})

    async def delete(
        self,
        group_id: str,
        *,
        req_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Delete a user group (admin required).

        Args:
            group_id: Group ID.
            req_id: Optional request ID.

        Returns:
            Deleted group dict.
        """
        params: dict[str, Any] = {"group_id": group_id}
        if req_id is not None:
            params["req_id"] = req_id
        response_data = await self.client._request(
            "DELETE", "/user_group_delete", params=params
        )
        return response_data.get("data", {})

    async def get(
        self,
        group_id: str,
        *,
        req_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Get a user group by ID.

        Args:
            group_id: Group ID.
            req_id: Optional request ID.

        Returns:
            Group dict.
        """
        params: dict[str, Any] = {"group_id": group_id}
        if req_id is not None:
            params["req_id"] = req_id
        response_data = await self.client._request(
            "GET", "/user_group_get_by_id", params=params
        )
        return response_data.get("data", {})

    async def list(
        self,
        *,
        flt: dict[str, Any] | None = None,
        req_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        List user groups.

        Args:
            flt: ``GulpCollabFilter`` dict for optional filtering.
            req_id: Optional request ID.

        Returns:
            List of group dicts.
        """
        params: dict[str, Any] = {}
        if req_id is not None:
            params["req_id"] = req_id
        response_data = await self.client._request(
            "POST", "/user_group_list", json=flt or {}, params=params or None
        )
        return response_data.get("data", [])

    async def add_user(
        self,
        group_id: str,
        user_id: str,
        *,
        req_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Add a user to a group (admin required).

        Args:
            group_id: Group ID.
            user_id: User ID to add.
            req_id: Optional request ID.

        Returns:
            Updated group dict.
        """
        params: dict[str, Any] = {"group_id": group_id, "user_id": user_id}
        if req_id is not None:
            params["req_id"] = req_id
        response_data = await self.client._request(
            "PATCH", "/user_group_add_user", params=params
        )
        return response_data.get("data", {})

    async def remove_user(
        self,
        group_id: str,
        user_id: str,
        *,
        req_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Remove a user from a group (admin required).

        Args:
            group_id: Group ID.
            user_id: User ID to remove.
            req_id: Optional request ID.

        Returns:
            Updated group dict.
        """
        params: dict[str, Any] = {"group_id": group_id, "user_id": user_id}
        if req_id is not None:
            params["req_id"] = req_id
        response_data = await self.client._request(
            "PATCH", "/user_group_remove_user", params=params
        )
        return response_data.get("data", {})
