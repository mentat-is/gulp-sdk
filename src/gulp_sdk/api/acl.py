"""
Object ACL API — manage who can access collaboration objects.

Gulp implements **least-privilege** access control on all collaboration
objects (notes, links, highlights, glyphs, operations, …).

By default:
- Collab objects (notes, links, highlights, …) are **public** — visible to
  everyone.  You can make them private so only the owner or an admin can see
  them.
- All other objects (operations, contexts, …) require explicit grants to be
  visible.

Quick example::

    async with GulpClient("http://localhost:8080") as client:
        await client.auth.login("admin", "admin")

        # Grant a user access to an operation
        await client.acl.add_granted_user("my_op_id", "operation", "alice")

        # Or grant a whole group
        await client.acl.add_granted_group("my_op_id", "operation", "analysts")

        # Make a note private (only owner/admin can read it)
        await client.acl.make_private("note_123", "note")
"""

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from gulp_sdk.client import GulpClient


class AclAPI:
    """
    Object-level access-control endpoints.

    The caller's token must be the **owner** of the target object or have
    ``admin`` permission for all write operations.
    """

    def __init__(self, client: "GulpClient") -> None:
        self.client = client

    async def add_granted_user(
        self,
        obj_id: str,
        obj_type: str,
        user_id: str,
        *,
        req_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Add *user_id* to the object's grants.

        Args:
            obj_id: ID of the object to modify.
            obj_type: Collab object type string (e.g. ``"note"``, ``"operation"``).
            user_id: User to grant access to.
            req_id: Optional request ID.

        Returns:
            Updated object dict.
        """
        params: dict[str, Any] = {
            "obj_id": obj_id,
            "obj_type": obj_type,
            "user_id": user_id,
        }
        if req_id is not None:
            params["req_id"] = req_id
        return (
            await self.client._request("PATCH", "/object_add_granted_user", params=params)
        ).get("data", {})

    async def remove_granted_user(
        self,
        obj_id: str,
        obj_type: str,
        user_id: str,
        *,
        req_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Remove *user_id* from the object's grants.

        Args:
            obj_id: ID of the object to modify.
            obj_type: Collab object type string.
            user_id: User to revoke.
            req_id: Optional request ID.

        Returns:
            Updated object dict.
        """
        params: dict[str, Any] = {
            "obj_id": obj_id,
            "obj_type": obj_type,
            "user_id": user_id,
        }
        if req_id is not None:
            params["req_id"] = req_id
        return (
            await self.client._request(
                "PATCH", "/object_remove_granted_user", params=params
            )
        ).get("data", {})

    async def add_granted_group(
        self,
        obj_id: str,
        obj_type: str,
        group_id: str,
        *,
        req_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Add *group_id* to the object's grants.

        Args:
            obj_id: ID of the object.
            obj_type: Collab object type string.
            group_id: Group to grant access to.
            req_id: Optional request ID.

        Returns:
            Updated object dict.
        """
        params: dict[str, Any] = {
            "obj_id": obj_id,
            "obj_type": obj_type,
            "group_id": group_id,
        }
        if req_id is not None:
            params["req_id"] = req_id
        return (
            await self.client._request(
                "PATCH", "/object_add_granted_group", params=params
            )
        ).get("data", {})

    async def remove_granted_group(
        self,
        obj_id: str,
        obj_type: str,
        group_id: str,
        *,
        req_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Remove *group_id* from the object's grants.

        Args:
            obj_id: ID of the object.
            obj_type: Collab object type string.
            group_id: Group to revoke.
            req_id: Optional request ID.

        Returns:
            Updated object dict.
        """
        params: dict[str, Any] = {
            "obj_id": obj_id,
            "obj_type": obj_type,
            "group_id": group_id,
        }
        if req_id is not None:
            params["req_id"] = req_id
        return (
            await self.client._request(
                "PATCH", "/object_remove_granted_group", params=params
            )
        ).get("data", {})

    async def make_private(
        self,
        obj_id: str,
        obj_type: str,
        *,
        req_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Make the object **private**.

        A private object is only accessible by the owner or administrators.

        Args:
            obj_id: ID of the object.
            obj_type: Collab object type string.
            req_id: Optional request ID.

        Returns:
            Updated object dict.
        """
        params: dict[str, Any] = {"obj_id": obj_id, "obj_type": obj_type}
        if req_id is not None:
            params["req_id"] = req_id
        return (
            await self.client._request("PATCH", "/object_make_private", params=params)
        ).get("data", {})

    async def make_public(
        self,
        obj_id: str,
        obj_type: str,
        *,
        req_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Make the object **public**.

        A public object has no explicit ``granted_user_ids`` or
        ``granted_user_group_ids`` — it is accessible by anyone.

        Args:
            obj_id: ID of the object.
            obj_type: Collab object type string.
            req_id: Optional request ID.

        Returns:
            Updated object dict.
        """
        params: dict[str, Any] = {"obj_id": obj_id, "obj_type": obj_type}
        if req_id is not None:
            params["req_id"] = req_id
        return (
            await self.client._request("PATCH", "/object_make_public", params=params)
        ).get("data", {})
