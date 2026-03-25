"""
Operations API — create, read, update, delete operations.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, AsyncIterator

from gulp.structs import GulpPluginParameters
from gulp_sdk.models import Operation
if TYPE_CHECKING:
    from gulp_sdk.client import GulpClient


class OperationsAPI:
    """Operations endpoints."""

    def __init__(self, client: "GulpClient") -> None:
        """Initialize with client reference."""
        self.client = client

    async def create(self, name: str, description: str | None = None) -> Operation:
        """
        Create a new operation.

        Args:
            name: Operation name
            description: Optional description

        Returns:
            Created Operation object
        """
        response_data = await self.client._request(
            "POST",
            "/operation_create",
            params={"name": name, "description": description} if description else {"name": name},
        )
        op_data = response_data.get("data", {})
        return Operation.model_validate(op_data)

    async def get(self, operation_id: str) -> Operation:
        """
        Get operation by ID.

        Args:
            operation_id: Operation ID

        Returns:
            Operation object

        Raises:
            NotFoundError: If operation not found
        """
        response_data = await self.client._request(
            "GET", "/operation_get_by_id", params={"operation_id": operation_id}
        )
        op_data = response_data.get("data", {})
        return Operation.model_validate(op_data)

    def list(self, limit: int = 50) -> AsyncIterator[Operation]:
        """
        List all operations with async pagination.

        Args:
            limit: Items per page

        Yields:
            Operation objects
        """
        async def _iter() -> AsyncIterator[Operation]:
            # Current backend returns the full operation list in one call.
            response_data = await self.client._request("POST", "/operation_list")
            data = response_data.get("data", [])
            if isinstance(data, list):
                count = 0
                for item in data:
                    yield Operation.model_validate(item)
                    count += 1
                    if count >= limit:
                        break

        return _iter()

    async def update(
        self,
        operation_id: str,
        name: str | None = None,
        description: str | None = None,
    ) -> Operation:
        """
        Update operation metadata.

        Args:
            operation_id: Operation ID
            name: New name (optional)
            description: New description (optional)

        Returns:
            Updated Operation object
        """
        if name is not None:
            raise ValueError("Operation name update is not supported by /operation_update")

        params = {"operation_id": operation_id}
        body = None
        if description is not None:
            body = {"description": description}

        response_data = await self.client._request(
            "PATCH",
            "/operation_update",
            params=params,
            json=body,
        )
        op_data = response_data.get("data", {})
        return Operation.model_validate(op_data)

    async def delete(self, operation_id: str) -> bool:
        """
        Delete an operation.

        Args:
            operation_id: Operation ID

        Returns:
            True if successful
        """
        await self.client._request(
            "DELETE",
            "/operation_delete",
            params={"operation_id": operation_id},
        )
        return True

    async def context_create(
        self,
        operation_id: str,
        context_name: str,
        *,
        color: str | None = None,
        glyph_id: str | None = None,
        fail_if_exists: bool = False,
        req_id: str | None = None,
    ) -> dict:
        """
        Create (or retrieve) a context within an operation.

        If a context with the same name already exists and ``fail_if_exists``
        is ``False`` (the default), the existing context is returned.

        Requires **ingest** permission.

        Args:
            operation_id: Parent operation ID.
            context_name: Name of the context to create.
            color: Optional CSS hex color (e.g. ``"#ff0000"``).
            glyph_id: Optional glyph ID.
            fail_if_exists: Raise an error if the context already exists.
            req_id: Optional request ID.

        Returns:
            Context dict with at least ``id`` and ``name`` keys.
        """
        from typing import Any

        params: dict[str, Any] = {
            "operation_id": operation_id,
            "context_name": context_name,
            "fail_if_exists": fail_if_exists,
        }
        if color is not None:
            params["color"] = color
        if glyph_id is not None:
            params["glyph_id"] = glyph_id
        if req_id is not None:
            params["req_id"] = req_id
        response_data = await self.client._request(
            "POST", "/context_create", params=params
        )
        return response_data.get("data", {})

    async def source_create(
        self,
        operation_id: str,
        context_id: str,
        source_name: str,
        *,
        plugin: str | None = None,
        plugin_params: GulpPluginParameters | None = None,
        color: str | None = None,
        glyph_id: str | None = None,
        fail_if_exists: bool = False,
        req_id: str | None = None,
    ) -> dict:
        """
        Create (or retrieve) a source within a context.

        If a source with the same name already exists and ``fail_if_exists``
        is ``False`` (the default), the existing source is returned.

        Requires **ingest** permission.

        Args:
            operation_id: Parent operation ID.
            context_id: Parent context ID.
            source_name: Name of the source to create.
            plugin: Optional plugin name.
            plugin_params: Optional plugin parameters.
            color: Optional CSS hex color.            
            glyph_id: Optional glyph ID.
            fail_if_exists: Raise an error if the source already exists.
            req_id: Optional request ID.

        Returns:
            Source dict with at least ``id`` and ``name`` keys.
        """
        from typing import Any

        params: dict[str, Any] = {
            "operation_id": operation_id,
            "context_id": context_id,
            "source_name": source_name,
            "fail_if_exists": fail_if_exists,
            "plugin": plugin,
        }
        if color is not None:
            params["color"] = color
        if glyph_id is not None:
            params["glyph_id"] = glyph_id
        if req_id is not None:
            params["req_id"] = req_id
        body = plugin_params.model_dump(exclude_none=True) if plugin_params else None
        response_data = await self.client._request(
            "POST", "/source_create", params=params, json=body
        )
        return response_data.get("data", {})

    async def operation_cleanup(
        self,
        operation_id: str,
        *,
        additional_tables: list[str] | None = None,
        req_id: str | None = None,
    ) -> dict:
        """
        Clean up an operation's collab objects and request stats without deleting the operation.

        Clears ``highlight``, ``note``, ``link``, and ``request_stats`` tables for the
        given operation.  Requires **admin** permission.

        Args:
            operation_id: Target operation.
            additional_tables: Extra collab table names to clear.
            req_id: Optional request ID.

        Returns:
            Dict with ``deleted`` count.
        """
        from typing import Any

        params: dict[str, Any] = {"operation_id": operation_id}
        if req_id is not None:
            params["req_id"] = req_id
        response_data = await self.client._request(
            "POST",
            "/operation_cleanup",
            params=params,
            json=additional_tables or None,
        )
        return response_data.get("data", {})

    # ------------------------------------------------------------------ #
    # Context management                                                   #
    # ------------------------------------------------------------------ #

    async def context_list(
        self,
        operation_id: str,
        *,
        req_id: str | None = None,
    ) -> list[dict]:
        """
        List all contexts for an operation.

        Args:
            operation_id: Parent operation ID.
            req_id: Optional request ID.

        Returns:
            List of context dicts.
        """
        from typing import Any

        params: dict[str, Any] = {"operation_id": operation_id}
        if req_id is not None:
            params["req_id"] = req_id
        response_data = await self.client._request(
            "GET", "/context_list", params=params
        )
        return response_data.get("data", [])

    async def context_get(
        self,
        obj_id: str,
        *,
        req_id: str | None = None,
    ) -> dict:
        """
        Get a context by its ID.

        Args:
            obj_id: Context ID.
            req_id: Optional request ID.

        Returns:
            Context dict.
        """
        from typing import Any

        params: dict[str, Any] = {"obj_id": obj_id}
        if req_id is not None:
            params["req_id"] = req_id
        response_data = await self.client._request(
            "GET", "/context_get_by_id", params=params
        )
        return response_data.get("data", {})

    async def context_delete(
        self,
        context_id: str,
        *,
        delete_data: bool = True,
        ws_id: str | None = None,
        req_id: str | None = None,
    ) -> dict:
        """
        Delete a context, optionally deleting all associated data.

        Requires **ingest** permission.

        Args:
            context_id: Context ID to delete.
            delete_data: If ``True`` (default), also deletes all documents and
                storage files associated with the context.
            ws_id: WebSocket ID for progress notifications.
            req_id: Optional request ID.

        Returns:
            Dict with ``id`` key.
        """
        from typing import Any

        params: dict[str, Any] = {
            "context_id": context_id,
            "delete_data": delete_data,
            "ws_id": ws_id or self.client.ws_id,
        }
        if req_id is not None:
            params["req_id"] = req_id
        response_data = await self.client._request(
            "DELETE", "/context_delete", params=params
        )
        return response_data.get("data", {})

    async def context_update(
        self,
        context_id: str,
        *,
        color: str | None = None,
        description: str | None = None,
        glyph_id: str | None = None,
        ws_id: str | None = None,
        req_id: str | None = None,
    ) -> dict:
        """
        Update a context's metadata.

        Requires **edit** permission.  At least one of ``color``,
        ``description``, or ``glyph_id`` must be provided.

        Args:
            context_id: Context ID.
            color: New CSS hex color (e.g. ``"#ff0000"``).
            description: New description.
            glyph_id: New glyph ID.
            ws_id: WebSocket ID.
            req_id: Optional request ID.

        Returns:
            Updated context dict.
        """
        from typing import Any

        params: dict[str, Any] = {
            "context_id": context_id,
            "ws_id": ws_id or self.client.ws_id,
        }
        if color is not None:
            params["color"] = color
        if description is not None:
            params["description"] = description
        if glyph_id is not None:
            params["glyph_id"] = glyph_id
        if req_id is not None:
            params["req_id"] = req_id
        response_data = await self.client._request(
            "PATCH", "/context_update", params=params
        )
        return response_data.get("data", {})

    # ------------------------------------------------------------------ #
    # Source management                                                    #
    # ------------------------------------------------------------------ #

    async def source_list(
        self,
        operation_id: str,
        context_id: str,
        *,
        req_id: str | None = None,
    ) -> list[dict]:
        """
        List all sources in a context.

        Args:
            operation_id: Parent operation ID.
            context_id: Parent context ID.
            req_id: Optional request ID.

        Returns:
            List of source dicts.
        """
        from typing import Any

        params: dict[str, Any] = {
            "operation_id": operation_id,
            "context_id": context_id,
        }
        if req_id is not None:
            params["req_id"] = req_id
        response_data = await self.client._request(
            "GET", "/source_list", params=params
        )
        return response_data.get("data", [])

    async def source_get(
        self,
        obj_id: str,
        *,
        req_id: str | None = None,
    ) -> dict:
        """
        Get a source by its ID.

        Args:
            obj_id: Source ID.
            req_id: Optional request ID.

        Returns:
            Source dict.
        """
        from typing import Any

        params: dict[str, Any] = {"obj_id": obj_id}
        if req_id is not None:
            params["req_id"] = req_id
        response_data = await self.client._request(
            "GET", "/source_get_by_id", params=params
        )
        return response_data.get("data", {})

    async def source_update(
        self,
        source_id: str,
        *,
        color: str | None = None,
        description: str | None = None,
        glyph_id: str | None = None,
        ws_id: str | None = None,
        req_id: str | None = None,
    ) -> dict:
        """
        Update a source's metadata.

        Requires **edit** permission.  At least one of ``color``,
        ``description``, or ``glyph_id`` must be provided.

        Args:
            source_id: Source ID.
            color: New CSS hex color.
            description: New description.
            glyph_id: New glyph ID.
            ws_id: WebSocket ID.
            req_id: Optional request ID.

        Returns:
            Updated source dict.
        """
        from typing import Any

        params: dict[str, Any] = {
            "source_id": source_id,
            "ws_id": ws_id or self.client.ws_id,
        }
        if color is not None:
            params["color"] = color
        if description is not None:
            params["description"] = description
        if glyph_id is not None:
            params["glyph_id"] = glyph_id
        if req_id is not None:
            params["req_id"] = req_id
        response_data = await self.client._request(
            "PATCH", "/source_update", params=params
        )
        return response_data.get("data", {})

    async def source_delete(
        self,
        source_id: str,
        *,
        delete_data: bool = True,
        ws_id: str | None = None,
        req_id: str | None = None,
    ) -> dict:
        """
        Delete a source, optionally deleting all associated data.

        Requires **ingest** permission.

        Args:
            source_id: Source ID to delete.
            delete_data: If ``True`` (default), also deletes all documents and
                storage files associated with the source.
            ws_id: WebSocket ID for progress notifications.
            req_id: Optional request ID.

        Returns:
            Dict with ``id`` key.
        """
        from typing import Any

        params: dict[str, Any] = {
            "source_id": source_id,
            "delete_data": delete_data,
            "ws_id": ws_id or self.client.ws_id,
        }
        if req_id is not None:
            params["req_id"] = req_id
        response_data = await self.client._request(
            "DELETE", "/source_delete", params=params
        )
        return response_data.get("data", {})

