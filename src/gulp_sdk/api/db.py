"""
OpenSearch / database admin API — index management and document rebase.

All endpoints require elevated permissions (``ingest`` or ``admin``).

Quick example::

    async with GulpClient("http://localhost:8080") as client:
        await client.auth.login("admin", "admin")

        # List all datastreams
        indexes = await client.db.list_indexes()

        # Refresh an index so new documents are searchable
        await client.db.refresh_index("test_operation")

        # Rebase documents by shifting timestamps +1 hour
        await client.db.rebase_by_query(
            "test_operation",
            ws_id=client.ws_id,
            offset_msec=3_600_000,
        )
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable
from gulp_sdk.api.request_utils import wait_for_request_stats

if TYPE_CHECKING:
    from gulp_sdk.client import GulpClient
    from gulp_sdk.websocket import WSMessage


class DbAPI:
    """
    OpenSearch index management and document rebase endpoints.

    Write operations require at least **ingest** permission.
    Index delete and listing require **admin** permission.
    """

    def __init__(self, client: "GulpClient") -> None:
        self.client = client

    async def rebase_by_query(
        self,
        operation_id: str,
        ws_id: str | None,
        offset_msec: int,
        *,
        flt: dict[str, Any] | None = None,
        script: str | None = None,
        req_id: str | None = None,
        wait: bool = False,
        timeout: int = 120,
        ws_callback: "Callable[[WSMessage], None] | None" = None,
    ) -> dict[str, Any]:
        """
        Rebase (shift) document timestamps in-place using ``update_by_query``.

        The default script shifts both ``@timestamp`` and ``gulp.timestamp``
        by ``offset_msec`` milliseconds.  A custom Painless ``script`` may be
        provided to override this behaviour.

        Requires **ingest** permission.  Progress is reported on ``ws_id``.

        Args:
            operation_id: Target operation.
            ws_id: WebSocket ID for progress notifications.
            offset_msec: Milliseconds to add to each timestamp (negative to
                subtract).
            flt: ``GulpQueryFilter`` dict to restrict which documents are
                rebased.
            script: Optional custom Painless script to run instead of the
                default rebase script.
            req_id: Optional request ID.

        Returns:
            ``{"status": "pending", "req_id": ...}``.
        """
        params: dict[str, Any] = {
            "operation_id": operation_id,
            "ws_id": ws_id or self.client.ws_id,
            "offset_msec": offset_msec,
        }
        if req_id is not None:
            params["req_id"] = req_id
        response_data = await self.client._request(
            "POST",
            "/opensearch_rebase_by_query",
            json=flt or {},
            params=params,
            data=script,
        )

        if (
            wait
            and isinstance(response_data, dict)
            and response_data.get("status") == "pending"
            and response_data.get("req_id")
        ):
            return await wait_for_request_stats(self.client, 
                str(response_data.get("req_id")), timeout, ws_callback=ws_callback
            )

        return response_data

    async def delete_index(
        self,
        index: str,
        *,
        delete_operation: bool = True,
        req_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Delete an OpenSearch datastream and its backing indexes.

        **WARNING**: all data in the index will be permanently deleted.

        Requires **admin** permission.

        Args:
            index: OpenSearch index / datastream name (usually equal to
                ``operation_id``).
            delete_operation: If ``True`` (default), also delete the
                corresponding collab operation if it exists.
            req_id: Optional request ID.

        Returns:
            Dict with ``index`` and ``operation_id`` keys.
        """
        params: dict[str, Any] = {
            "index": index,
            "delete_operation": delete_operation,
        }
        if req_id is not None:
            params["req_id"] = req_id
        response_data = await self.client._request(
            "DELETE", "/opensearch_delete_index", params=params
        )
        return response_data.get("data", {})

    async def list_indexes(
        self,
        *,
        req_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        List all available OpenSearch datastreams.

        Requires **admin** permission.

        Args:
            req_id: Optional request ID.

        Returns:
            List of datastream dicts with ``name``, ``count``, ``indexes``,
            and ``template`` keys.
        """
        params: dict[str, Any] = {}
        if req_id is not None:
            params["req_id"] = req_id
        response_data = await self.client._request(
            "GET", "/opensearch_list_index", params=params or None
        )
        return response_data.get("data", [])

    async def refresh_index(
        self,
        index: str,
        *,
        req_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Refresh an OpenSearch datastream/index.

        Makes all operations since the last refresh available for search.
        Requires **ingest** permission.

        Args:
            index: OpenSearch index / datastream name.
            req_id: Optional request ID.

        Returns:
            Dict with ``index`` key confirming the operation.
        """
        params: dict[str, Any] = {"index": index}
        if req_id is not None:
            params["req_id"] = req_id
        response_data = await self.client._request(
            "POST", "/opensearch_refresh_index", params=params
        )
        return response_data.get("data", {})
