"""
Enrichment API — enrich documents, add/remove tags and custom fields.

All enrichment operations are asynchronous; results stream to the WebSocket.
``enrich_single_id`` is the exception and returns data synchronously.

Quick example::

    async with GulpClient("http://localhost:8080") as client:
        await client.auth.login("user", "pass")

        # Tag multiple documents matching a filter
        result = await client.enrich.tag_documents(
            operation_id="my_op",
            tags=["malware", "suspicious"],
            flt={"context_ids": ["ctx1"]},
        )

        # Enrich a single document via plugin
        doc = await client.enrich.enrich_single_id(
            operation_id="my_op",
            doc_id="abc123",
            plugin="my_enricher",
            fields={"threat_score": 0.9},
        )
"""

from typing import TYPE_CHECKING, Any
from gulp_sdk.api.request_utils import wait_for_request_stats

if TYPE_CHECKING:
    from gulp_sdk.client import GulpClient


class EnrichAPI:
    """
    Document enrichment endpoints.

    Requires **ingest** permission for ``enrich_documents`` and related bulk
    operations.
    """

    def __init__(self, client: "GulpClient") -> None:
        self.client = client

    async def enrich_documents(
        self,
        operation_id: str,
        plugin: str,
        fields: dict[str, Any],
        *,
        ws_id: str | None = None,
        flt: dict[str, Any] | None = None,
        plugin_params: dict[str, Any] | None = None,
        req_id: str | None = None,
        wait: bool = False,
        timeout: int = 120,
    ) -> dict[str, Any]:
        """
        Enrich multiple documents matching a filter using a plugin (async).

        Args:
            operation_id: Target operation.
            plugin: Enrichment plugin name.
            fields: Fields to set/update on matching documents.
            ws_id: WebSocket ID.
            flt: ``GulpQueryFilter`` dict to select documents.
            plugin_params: ``GulpPluginParameters`` dict.
            req_id: Optional request ID.

        Returns:
            ``{"status": "pending", "req_id": ...}``.
        """
        params: dict[str, Any] = {
            "operation_id": operation_id,
            "plugin": plugin,
            "ws_id": ws_id or self.client.ws_id,
        }
        if req_id is not None:
            params["req_id"] = req_id
        body: dict[str, Any] = {"fields": fields}
        if flt:
            body["flt"] = flt
        if plugin_params:
            body["plugin_params"] = plugin_params
        response_data = await self.client._request(
            "POST", "/enrich_documents", json=body, params=params
        )

        if (
            wait
            and isinstance(response_data, dict)
            and response_data.get("status") == "pending"
            and response_data.get("req_id")
        ):
            return await wait_for_request_stats(
                self.client, str(response_data.get("req_id")), timeout
            )

        return response_data

    async def enrich_single_id(
        self,
        operation_id: str,
        doc_id: str,
        plugin: str,
        fields: dict[str, Any],
        *,
        ws_id: str | None = None,
        plugin_params: dict[str, Any] | None = None,
        req_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Enrich a single document by its OpenSearch ``_id`` (synchronous).

        Args:
            operation_id: Target operation.
            doc_id: Document ``_id``.
            plugin: Enrichment plugin name.
            fields: Fields to set/update.
            ws_id: WebSocket ID.
            plugin_params: ``GulpPluginParameters`` dict.
            req_id: Optional request ID.

        Returns:
            Updated document dict.
        """
        params: dict[str, Any] = {
            "operation_id": operation_id,
            "doc_id": doc_id,
            "plugin": plugin,
            "ws_id": ws_id or self.client.ws_id,
        }
        if req_id is not None:
            params["req_id"] = req_id
        body: dict[str, Any] = {"fields": fields}
        if plugin_params:
            body["plugin_params"] = plugin_params
        response_data = await self.client._request(
            "POST", "/enrich_single_id", json=body, params=params
        )
        return response_data.get("data", {})

    async def update_documents(
        self,
        operation_id: str,
        fields: dict[str, Any],
        *,
        ws_id: str | None = None,
        flt: dict[str, Any] | None = None,
        req_id: str | None = None,
        wait: bool = False,
        timeout: int = 120,
    ) -> dict[str, Any]:
        """
        Directly update fields on multiple documents (async, no plugin).

        Args:
            operation_id: Target operation.
            fields: Fields to set.
            ws_id: WebSocket ID.
            flt: ``GulpQueryFilter`` dict.
            req_id: Optional request ID.
            wait: If True, wait for the async request to complete and return final status.
            timeout: Max seconds to wait if ``wait`` is True (0 for no timeout).

        Returns:
            ``{"status": "pending", "req_id": ...}``.
        """
        params: dict[str, Any] = {
            "operation_id": operation_id,
            "ws_id": ws_id or self.client.ws_id,
        }
        if req_id is not None:
            params["req_id"] = req_id
        # Server expects body key `data` (not `fields`) plus optional `flt`.
        body: dict[str, Any] = {"data": fields}
        if flt:
            body["flt"] = flt
        response_data = await self.client._request(
            "POST", "/update_documents", json=body, params=params
        )
        # Optionally wait for completion of the async request
        if wait and isinstance(response_data, dict) and response_data.get("status") == "pending":
            req = response_data.get("req_id")
            if req:
                return await wait_for_request_stats(self.client, str(req), timeout)

        return response_data

    async def update_single_id(
        self,
        operation_id: str,
        doc_id: str,
        fields: dict[str, Any],
        *,
        ws_id: str | None = None,
        req_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Update fields on a single document by ID (synchronous, no plugin).

        Args:
            operation_id: Target operation.
            doc_id: Document ``_id``.
            fields: Fields to set.
            ws_id: WebSocket ID.
            req_id: Optional request ID.

        Returns:
            Updated document dict.
        """
        params: dict[str, Any] = {
            "operation_id": operation_id,
            "doc_id": doc_id,
            "ws_id": ws_id or self.client.ws_id,
        }
        if req_id is not None:
            params["req_id"] = req_id
        # Server expects body key `data` for update payload.
        response_data = await self.client._request(
            "POST", "/update_single_id", json={"data": fields}, params=params
        )
        return response_data.get("data", {})

    async def tag_documents(
        self,
        operation_id: str,
        tags: list[str],
        *,
        ws_id: str | None = None,
        flt: dict[str, Any] | None = None,
        req_id: str | None = None,
        wait: bool = False,
        timeout: int = 120,
    ) -> dict[str, Any]:
        """
        Add tags to multiple documents matching a filter (async).

        Args:
            operation_id: Target operation.
            tags: Tags to add.
            ws_id: WebSocket ID.
            flt: ``GulpQueryFilter`` dict.
            req_id: Optional request ID.
            wait: If True, wait for the async request to complete and return final status.
            timeout: Max seconds to wait if ``wait`` is True (0 for no timeout).

        Returns:
            ``{"status": "pending", "req_id": ...}``.
        """
        params: dict[str, Any] = {
            "operation_id": operation_id,
            "ws_id": ws_id or self.client.ws_id,
        }
        if req_id is not None:
            params["req_id"] = req_id
        body: dict[str, Any] = {"tags": tags}
        if flt:
            body["flt"] = flt
        response_data = await self.client._request(
            "POST", "/tag_documents", json=body, params=params
        )
        # Optionally wait for completion of the async request
        if wait and isinstance(response_data, dict) and response_data.get("status") == "pending":
            req = response_data.get("req_id")
            if req:
                return await wait_for_request_stats(self.client, str(req), timeout)

        return response_data

    async def tag_single_id(
        self,
        operation_id: str,
        doc_id: str,
        tags: list[str],
        *,
        ws_id: str | None = None,
        req_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Add tags to a single document by ID (synchronous).

        Args:
            operation_id: Target operation.
            doc_id: Document ``_id``.
            tags: Tags to add.
            ws_id: WebSocket ID.
            req_id: Optional request ID.

        Returns:
            Updated document dict.
        """
        params: dict[str, Any] = {
            "operation_id": operation_id,
            "doc_id": doc_id,
            "ws_id": ws_id or self.client.ws_id,
        }
        if req_id is not None:
            params["req_id"] = req_id
        response_data = await self.client._request(
            "POST", "/tag_single_id", json=tags, params=params
        )
        return response_data.get("data", {})

    async def enrich_remove(
        self,
        operation_id: str,
        field: str,
        *,
        ws_id: str | None = None,
        flt: dict[str, Any] | None = None,
        req_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Remove an enrichment field from documents matching a filter (async).

        Args:
            operation_id: Target operation.
            field: Field name to remove.
            ws_id: WebSocket ID.
            flt: ``GulpQueryFilter`` dict.
            req_id: Optional request ID.

        Returns:
            ``{"status": "pending", "req_id": ...}``.
        """
        params: dict[str, Any] = {
            "operation_id": operation_id,
            "field": field,
            "ws_id": ws_id or self.client.ws_id,
        }
        if req_id is not None:
            params["req_id"] = req_id
        response_data = await self.client._request(
            "POST", "/enrich_remove", json=flt or {}, params=params
        )
        return response_data
