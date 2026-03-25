"""
Queries API — OpenSearch DSL, Gulp filters, external sources, Sigma rules.

All query endpoints except ``query_single_id`` and ``query_aggregation`` are
**asynchronous**: the server returns ``pending`` immediately and streams results
to the WebSocket identified by ``ws_id``.  Use ``preview_mode=True`` inside
``q_options`` to run synchronously (limited result set).

Quick example::

    async with GulpClient("http://localhost:8080") as client:
        await client.auth.login("user", "pass")

        # Simple Gulp filter query
        result = await client.queries.query_gulp(
            operation_id="my_op",
            flt={"operation_ids": ["my_op"]},
        )

        # Raw OpenSearch DSL
        result = await client.queries.query_raw(
            operation_id="my_op",
            q=[{"query": {"match_all": {}}}],
            q_options={"name": "all-events"},
        )

        # Get a single document
        doc = await client.queries.query_single_id(
            operation_id="my_op",
            doc_id="abc123",
        )
"""

import inspect
from typing import TYPE_CHECKING, Any

from gulp_sdk.api.request_utils import wait_for_request_stats

if TYPE_CHECKING:
    from gulp_sdk.client import GulpClient


class QueriesAPI:
    """
    Query endpoints: raw DSL, gulp filter, external, sigma, aggregation, etc.

    For async queries the server returns ``{"status": "pending", "req_id": ...}``.
    Results are delivered to the WebSocket.  Set ``q_options["preview_mode"] = True``
    for synchronous small result sets.
    """

    def __init__(self, client: "GulpClient") -> None:
        self.client = client

    async def query_raw(
        self,
        operation_id: str,
        q: list[dict[str, Any]],
        *,
        ws_id: str | None = None,
        q_options: dict[str, Any] | None = None,
        req_id: str | None = None,
        wait: bool = False,
        timeout: int = 120,
    ) -> dict[str, Any]:
        """
        Query Gulp using raw OpenSearch DSL.

        Runs one or more queries and streams matching documents back via
        WebSocket (or returns them directly when ``q_options["preview_mode"]``
        is ``True``).

        Args:
            operation_id: Target operation.
            q: List of OpenSearch DSL query dicts.
            ws_id: WebSocket ID (defaults to client ws_id).
            q_options: ``GulpQueryParameters`` dict — supports pagination,
                field filtering, sorting, ``preview_mode``, ``name``,
                ``create_notes``, etc.
            req_id: Optional request ID.

        Returns:
            ``{"status": "pending", "req_id": ...}`` for async mode, or
            ``{"total_hits": n, "docs": [...]}`` in preview mode.
        """
        params: dict[str, Any] = {
            "operation_id": operation_id,
            "ws_id": ws_id or self.client.ws_id,
        }
        if req_id is not None:
            params["req_id"] = req_id
        body: dict[str, Any] = {"q": q}
        if q_options:
            body["q_options"] = q_options
        response_data = await self.client._request(
            "POST", "/query_raw", json=body, params=params
        )

        if (
            wait
            and isinstance(response_data, dict)
            and response_data.get("status") == "pending"
            and response_data.get("req_id")
        ):
            return await wait_for_request_stats(self.client, 
                str(response_data.get("req_id")), timeout
            )

        return response_data

    async def query_gulp(
        self,
        operation_id: str,
        *,
        ws_id: str | None = None,
        flt: dict[str, Any] | None = None,
        q_options: dict[str, Any] | None = None,
        req_id: str | None = None,
        wait: bool = False,
        timeout: int = 120,
    ) -> dict[str, Any]:
        """
        Query Gulp using the simplified ``GulpQueryFilter`` format.

        Suitable for straightforward queries by operation/context/source/time
        range and keyword.  For complex queries use :meth:`query_raw`.

        Args:
            operation_id: Target operation (``flt.operation_ids`` is set
                automatically).
            ws_id: WebSocket ID.
            flt: ``GulpQueryFilter`` dict (``operation_ids``, ``context_ids``,
                ``source_ids``, ``time_range``, ``must``, etc.).
            q_options: ``GulpQueryParameters`` dict.
            req_id: Optional request ID.

        Returns:
            ``{"status": "pending", "req_id": ...}`` or preview data.
        """
        params: dict[str, Any] = {
            "operation_id": operation_id,
            "ws_id": ws_id or self.client.ws_id,
        }
        if req_id is not None:
            params["req_id"] = req_id
        body: dict[str, Any] = {}
        if flt:
            body["flt"] = flt
        if q_options:
            body["q_options"] = q_options
        response_data = await self.client._request(
            "POST", "/query_gulp", json=body, params=params
        )

        if (
            wait
            and isinstance(response_data, dict)
            and response_data.get("status") == "pending"
            and response_data.get("req_id")
        ):
            return await wait_for_request_stats(self.client, 
                str(response_data.get("req_id")), timeout
            )

        return response_data

    async def query_external(
        self,
        operation_id: str,
        q: Any,
        plugin: str,
        plugin_params: dict[str, Any],
        *,
        ws_id: str | None = None,
        q_options: dict[str, Any] | None = None,
        req_id: str | None = None,
        wait: bool = False,
        timeout: int = 120,
    ) -> dict[str, Any]:
        """
        Query an external data source and ingest results into Gulp.

        Requires **ingest** permission (unless ``preview_mode`` is set).

        Args:
            operation_id: Target operation for ingested documents.
            q: Query in the source's native query language.
            plugin: Plugin name (e.g. ``"query_elasticsearch"``).
            plugin_params: ``GulpPluginParameters`` dict — must include all
                parameters needed to connect to the external source via
                ``custom_parameters``.
            ws_id: WebSocket ID.
            q_options: ``GulpQueryParameters`` dict.
            req_id: Optional request ID.

        Returns:
            ``{"status": "pending", "req_id": ...}`` or preview data.
        """
        params: dict[str, Any] = {
            "operation_id": operation_id,
            "plugin": plugin,
            "ws_id": ws_id or self.client.ws_id,
        }
        if req_id is not None:
            params["req_id"] = req_id
        body: dict[str, Any] = {"q": q, "plugin_params": plugin_params}
        if q_options:
            body["q_options"] = q_options
        response_data = await self.client._request(
            "POST", "/query_external", json=body, params=params
        )

        if (
            wait
            and isinstance(response_data, dict)
            and response_data.get("status") == "pending"
            and response_data.get("req_id")
        ):
            return await wait_for_request_stats(self.client, 
                str(response_data.get("req_id")), timeout
            )

        return response_data

    async def query_sigma(
        self,
        operation_id: str,
        sigmas: list[str],
        src_ids: list[str],
        *,
        ws_id: str | None = None,
        levels: list[str] | None = None,
        products: list[str] | None = None,
        categories: list[str] | None = None,
        services: list[str] | None = None,
        tags: list[str] | None = None,
        q_options: dict[str, Any] | None = None,
        req_id: str | None = None,
        wait: bool = False,
        timeout: int = 120,
    ) -> dict[str, Any]:
        """
        Query using Sigma rules.

        Each Sigma rule in ``sigmas`` is converted to an OpenSearch query and
        run concurrently.

        Args:
            operation_id: Target operation.
            sigmas: List of Sigma rule YAML strings.
            src_ids: Source IDs to apply rules to (use ``[]`` for all sources).
            ws_id: WebSocket ID.
            levels: Filter sigma rules by level (e.g. ``["high", "critical"]``).
            products: Filter by ``sigma.logsource.product``.
            categories: Filter by ``sigma.logsource.category``.
            services: Filter by ``sigma.logsource.service``.
            tags: Filter by ``sigma.tags``.
            q_options: ``GulpQueryParameters`` dict.
            req_id: Optional request ID.

        Returns:
            ``{"status": "pending", "req_id": ...}`` or preview data.
        """
        params: dict[str, Any] = {
            "operation_id": operation_id,
            "ws_id": ws_id or self.client.ws_id,
        }
        if req_id is not None:
            params["req_id"] = req_id
        body: dict[str, Any] = {"sigmas": sigmas, "src_ids": src_ids}
        if levels is not None:
            body["levels"] = levels
        if products is not None:
            body["products"] = products
        if categories is not None:
            body["categories"] = categories
        if services is not None:
            body["services"] = services
        if tags is not None:
            body["tags"] = tags
        if q_options:
            body["q_options"] = q_options
        response_data = await self.client._request(
            "POST", "/query_sigma", json=body, params=params
        )

        if (
            wait
            and isinstance(response_data, dict)
            and response_data.get("status") == "pending"
            and response_data.get("req_id")
        ):
            return await wait_for_request_stats(self.client, 
                str(response_data.get("req_id")), timeout
            )

        return response_data

    async def query_sigma_zip(
        self,
        operation_id: str,
        zip_path: str,
        *,
        src_ids: list[str] | None = None,
        ws_id: str | None = None,
        levels: list[str] | None = None,
        products: list[str] | None = None,
        categories: list[str] | None = None,
        services: list[str] | None = None,
        tags: list[str] | None = None,
        q_options: dict[str, Any] | None = None,
        req_id: str | None = None,
        wait: bool = False,
        timeout: int = 120,
    ) -> dict[str, Any]:
        """
        Query using a ZIP archive containing Sigma rules.

        This endpoint is provided by the optional ``query_sigma_zip`` extension
        plugin and may be unavailable in core-only deployments.

        Args:
            operation_id: Target operation.
            zip_path: Local path to a ``.zip`` with Sigma YAML files.
            src_ids: Source IDs to scope query execution.
            ws_id: WebSocket ID.
            levels: Filter sigma rules by level.
            products: Filter by ``sigma.logsource.product``.
            categories: Filter by ``sigma.logsource.category``.
            services: Filter by ``sigma.logsource.service``.
            tags: Filter by ``sigma.tags``.
            q_options: ``GulpQueryParameters`` dict.
            req_id: Optional request ID.

        Returns:
            ``{"status": "pending", "req_id": ...}`` when accepted.
        """
        import json
        from pathlib import Path

        zip_obj = Path(zip_path)
        zip_bytes = zip_obj.read_bytes()

        payload: dict[str, Any] = {"src_ids": src_ids or []}
        if levels is not None:
            payload["levels"] = levels
        if products is not None:
            payload["products"] = products
        if categories is not None:
            payload["categories"] = categories
        if services is not None:
            payload["services"] = services
        if tags is not None:
            payload["tags"] = tags
        if q_options:
            payload["q_options"] = q_options

        files = [
            ("payload", ("payload.json", json.dumps(payload), "application/json")),
            ("f", (zip_obj.name, zip_bytes, "application/zip")),
        ]

        params: dict[str, Any] = {
            "operation_id": operation_id,
            "ws_id": ws_id or self.client.ws_id,
        }
        if req_id is not None:
            params["req_id"] = req_id

        response_data = await self.client._request(
            "POST",
            "/query_sigma_zip",
            files=files,
            headers={"size": str(len(zip_bytes))},
            params=params,
        )

        if (
            wait
            and isinstance(response_data, dict)
            and response_data.get("status") == "pending"
            and response_data.get("req_id")
        ):
            return await wait_for_request_stats(self.client, 
                str(response_data.get("req_id")), timeout
            )

        return response_data

    async def query_single_id(
        self,
        operation_id: str,
        doc_id: str,
        *,
        req_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Retrieve a single document by its OpenSearch ``_id``.

        Args:
            operation_id: Parent operation (determines the index).
            doc_id: Document ``_id`` in OpenSearch.
            req_id: Optional request ID.

        Returns:
            Document dict (synchronous).
        """
        params: dict[str, Any] = {"operation_id": operation_id, "doc_id": doc_id}
        if req_id is not None:
            params["req_id"] = req_id
        response_data = await self.client._request(
            "POST", "/query_single_id", params=params
        )
        return response_data.get("data", {})

    async def query_aggregation(
        self,
        operation_id: str,
        q: dict[str, Any],
        *,
        req_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Run an OpenSearch aggregation query (synchronous).

        Args:
            operation_id: Target operation.
            q: OpenSearch aggregation query dict.
            req_id: Optional request ID.

        Returns:
            ``{"aggregations": {...}}`` dict.
        """
        params: dict[str, Any] = {"operation_id": operation_id}
        if req_id is not None:
            params["req_id"] = req_id
        response_data = await self.client._request(
            "POST", "/query_aggregation", json=q, params=params
        )
        return response_data.get("data", {})

    async def query_history_get(
        self,
        *,
        req_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Get the query history for the currently authenticated user.

        Returns:
            List of ``GulpUserDataQueryHistoryEntry`` dicts.
        """
        params: dict[str, Any] = {}
        if req_id is not None:
            params["req_id"] = req_id
        response_data = await self.client._request(
            "GET", "/query_history_get", params=params or None
        )
        return response_data.get("data", [])

    async def query_max_min_per_field(
        self,
        operation_id: str,
        *,
        flt: dict[str, Any] | None = None,
        group_by: str | None = None,
        req_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Get max/min ``@timestamp`` and ``event.code`` across documents.

        Returns per-source bucketed stats useful for timeline rendering.

        Args:
            operation_id: Target operation.
            flt: ``GulpQueryFilter`` dict for optional restriction.
            group_by: Field to group by (e.g. ``"event.code"``).
            req_id: Optional request ID.

        Returns:
            Dict with ``buckets`` and ``total`` keys.
        """
        params: dict[str, Any] = {"operation_id": operation_id}
        if group_by is not None:
            params["group_by"] = group_by
        if req_id is not None:
            params["req_id"] = req_id
        response_data = await self.client._request(
            "POST", "/query_max_min_per_field", json=flt or {}, params=params
        )
        return response_data.get("data", {})

    async def query_operations(
        self,
        *,
        req_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Get all operations with aggregated context/source/field stats.

        Returns operations with their contexts, sources, and per-source max/min
        ``event.code`` and ``gulp.timestamp`` values.

        Returns:
            List of operation dicts with nested context/source structure.
        """
        params: dict[str, Any] = {}
        if req_id is not None:
            params["req_id"] = req_id
        response_data = await self.client._request(
            "GET", "/query_operations", params=params or None
        )
        return response_data.get("data", [])

    async def query_fields_by_source(
        self,
        operation_id: str,
        context_id: str,
        source_id: str,
        *,
        req_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Get the field → type mapping for a specific source.

        If the mapping is not yet cached, an empty dict is returned and a
        background worker is spawned to compute it — the client should retry.

        Args:
            operation_id: Parent operation.
            context_id: Parent context.
            source_id: Source to inspect.
            req_id: Optional request ID.

        Returns:
            Dict mapping field names to their OpenSearch type strings, or
            ``{}`` if not yet available.
        """
        params: dict[str, Any] = {
            "operation_id": operation_id,
            "context_id": context_id,
            "source_id": source_id,
        }
        if req_id is not None:
            params["req_id"] = req_id
        response_data = await self.client._request(
            "GET", "/query_fields_by_source", params=params
        )
        return response_data.get("data", {})

    async def query_gulp_export_json(
        self,
        operation_id: str,
        output_path: str,
        *,
        flt: dict[str, Any] | None = None,
        q_options: dict[str, Any] | None = None,
        req_id: str | None = None,
    ) -> str:
        """
        Export documents as a JSON file (synchronous, streaming download).

        Performs the same query as :meth:`query_gulp` but streams the results
        as a JSON file to the caller instead of sending them over WebSocket.

        Args:
            operation_id: Target operation.
            output_path: Local path where the JSON file will be saved.
            flt: ``GulpQueryFilter`` dict.
            q_options: ``GulpQueryParameters`` dict.
            req_id: Optional request ID.

        Returns:
            ``output_path`` on success.
        """
        params: dict[str, Any] = {"operation_id": operation_id}
        if req_id is not None:
            params["req_id"] = req_id
        body: dict[str, Any] = {}
        if flt:
            body["flt"] = flt
        if q_options:
            body["q_options"] = q_options

        req_headers: dict[str, str] = {}
        if self.client.token:
            req_headers["token"] = self.client.token
        resp = await self.client._client.post(
            "/query_gulp_export_json",
            params=params,
            json=body or None,
            headers=req_headers,
        )
        if resp.status_code >= 400:
            maybe = self.client._raise_for_status(
                resp.status_code, resp.json() if resp.content else {}
            )
            if inspect.isawaitable(maybe):
                await maybe
        with open(output_path, "wb") as f:
            f.write(resp.content)
        return output_path

