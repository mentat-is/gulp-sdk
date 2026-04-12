"""
Plugins and utility API — plugin management, mapping files, request stats.

Provides access to plugin management (list, upload, download, delete),
mapping-file management, server version, and request lifecycle.

Quick example::

    async with GulpClient("http://localhost:8080") as client:
        await client.auth.login("admin", "admin")

        # List all installed plugins
        plugins = await client.plugins.list()

        # Upload a custom plugin
        await client.plugins.upload(
            "/path/to/my_plugin.py", plugin_type="default"
        )

        # List available mapping files
        mappings = await client.plugins.mapping_list()

        # Get server version
        ver = await client.plugins.version()
"""

from __future__ import annotations

import inspect
from typing import TYPE_CHECKING, Any, Literal
if TYPE_CHECKING:
    from gulp_sdk.client import GulpClient


class PluginsAPI:
    """
    Plugin management, mapping files, server utility, and request-stats endpoints.

    Write operations (upload, delete) require **admin** permission.
    """

    def __init__(self, client: "GulpClient") -> None:
        self.client = client

    # ------------------------------------------------------------------ #
    # Plugin management                                                    #
    # ------------------------------------------------------------------ #

    async def list(self, *, req_id: str | None = None) -> list[dict[str, Any]]:
        """
        List all available plugins (ingestion, enrichment, extension, …).

        Returns:
            List of plugin-entry dicts with ``filename``, ``display_name``,
            ``type``, ``desc``, ``sigma_support``, etc.
        """
        params: dict[str, Any] = {}
        if req_id is not None:
            params["req_id"] = req_id
        response = await self.client._request("GET", "/plugin_list", params=params or None)
        return response.get("data", [])

    async def list_ui(self, *, req_id: str | None = None) -> list[dict[str, Any]]:
        """
        List available UI plugins.

        Returns:
            List of UI-plugin-entry dicts.
        """
        params: dict[str, Any] = {}
        if req_id is not None:
            params["req_id"] = req_id
        response = await self.client._request(
            "GET", "/ui_plugin_list", params=params or None
        )
        return response.get("data", [])

    async def upload(
        self,
        file_path: str,
        *,
        plugin_type: Literal["default", "extension", "ui"] = "default",
        fail_if_exists: bool = False,
        req_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Upload one or more plugin files to the server.

        Args:
            file_path: Local path to the plugin ``.py`` file.
            plugin_type: Plugin type category — ``"default"``,
                ``"extension"``, or ``"ui"``.
            fail_if_exists: Raise an error if a file with the same name
                already exists (default: overwrite).
            req_id: Optional request ID.

        Returns:
            Dict with ``file_paths`` key listing saved paths on the server.
        """
        params: dict[str, Any] = {
            "plugin_type": plugin_type,
            "fail_if_exists": fail_if_exists,
        }
        if req_id is not None:
            params["req_id"] = req_id
        with open(file_path, "rb") as f:
            files = {"files": (file_path.split("/")[-1], f, "application/octet-stream")}
            response = await self.client._request(
                "POST", "/plugin_upload", params=params, files=files
            )
        return response.get("data", {})

    async def delete(
        self,
        filename: str,
        *,
        plugin_type: Literal["default", "extension", "ui"] = "default",
        req_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Delete a plugin file from the server.

        Args:
            filename: Filename of the plugin, e.g. ``"my_plugin.py"``.
            plugin_type: Plugin type category.
            req_id: Optional request ID.

        Returns:
            Confirmation dict with ``deleted`` key.
        """
        params: dict[str, Any] = {"filename": filename, "plugin_type": plugin_type}
        if req_id is not None:
            params["req_id"] = req_id
        return (
            await self.client._request("DELETE", "/plugin_delete", params=params)
        ).get("data", {})

    async def download(
        self,
        filename: str,
        output_path: str,
        *,
        plugin_type: Literal["default", "extension", "ui"] = "default",
        req_id: str | None = None,
    ) -> str:
        """
        Download a plugin file from the server.

        Args:
            filename: Filename of the plugin to download.
            output_path: Local path to save the downloaded file.
            plugin_type: Plugin type category.
            req_id: Optional request ID.

        Returns:
            ``output_path`` on success.
        """
        params: dict[str, Any] = {"filename": filename, "plugin_type": plugin_type}
        if req_id is not None:
            params["req_id"] = req_id
        req_headers: dict[str, str] = {}
        if self.client.token:
            req_headers["token"] = self.client.token
        resp = await self.client._client.get(
            "/plugin_download", params=params, headers=req_headers
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

    # ------------------------------------------------------------------ #
    # Mapping files                                                        #
    # ------------------------------------------------------------------ #

    async def mapping_list(self, *, req_id: str | None = None) -> list[dict[str, Any]]:
        """
        List all available mapping files.

        Returns:
            List of dicts with ``filename``, ``path``, ``metadata``, and
            ``mapping_ids`` keys.
        """
        params: dict[str, Any] = {}
        if req_id is not None:
            params["req_id"] = req_id
        response = await self.client._request(
            "GET", "/mapping_file_list", params=params or None
        )
        return response.get("data", [])

    async def mapping_upload(
        self,
        file_path: str,
        *,
        fail_if_exists: bool = False,
        req_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Upload a mapping JSON file to the server.

        Args:
            file_path: Local path to the mapping ``.json`` file.
            fail_if_exists: Raise an error if the file already exists.
            req_id: Optional request ID.

        Returns:
            Dict with ``path`` key showing where the file was saved.
        """
        params: dict[str, Any] = {"fail_if_exists": fail_if_exists}
        if req_id is not None:
            params["req_id"] = req_id
        with open(file_path, "rb") as f:
            files = {"file": (file_path.split("/")[-1], f, "application/json")}
            response = await self.client._request(
                "POST", "/mapping_file_upload", params=params, files=files
            )
        return response.get("data", {})

    async def mapping_download(
        self,
        filename: str,
        output_path: str,
        *,
        req_id: str | None = None,
    ) -> str:
        """
        Download a mapping file from the server.

        Args:
            filename: Filename to download, e.g. ``"windows.json"``.
            output_path: Local path to save the file.
            req_id: Optional request ID.

        Returns:
            ``output_path`` on success.
        """
        params: dict[str, Any] = {"filename": filename}
        if req_id is not None:
            params["req_id"] = req_id
        req_headers: dict[str, str] = {}
        if self.client.token:
            req_headers["token"] = self.client.token
        resp = await self.client._client.get(
            "/mapping_file_download", params=params, headers=req_headers
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

    async def mapping_delete(
        self,
        filename: str,
        *,
        req_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Delete a mapping file from the server's extra mapping path.

        Args:
            filename: Filename to delete, e.g. ``"custom_mapping.json"``.
            req_id: Optional request ID.

        Returns:
            Confirmation dict with ``deleted`` key.
        """
        params: dict[str, Any] = {"filename": filename}
        if req_id is not None:
            params["req_id"] = req_id
        return (
            await self.client._request("DELETE", "/mapping_file_delete", params=params)
        ).get("data", {})

    # ------------------------------------------------------------------ #
    # Server utility                                                       #
    # ------------------------------------------------------------------ #

    async def version(self, *, req_id: str | None = None) -> str:
        """
        Get the Gulp server version string.

        Returns:
            Version string, e.g. ``"gulp v0.0.9 (muty v0.2)"``.
        """
        params: dict[str, Any] = {}
        if req_id is not None:
            params["req_id"] = req_id
        response = await self.client._request("GET", "/version", params=params or None)
        return response.get("data", {}).get("version", "")

    # ------------------------------------------------------------------ #
    # Request stats                                                        #
    # ------------------------------------------------------------------ #

    async def request_get(
        self,
        obj_id: str,
        *,
        req_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Get request stats by request/object ID.

        Args:
            obj_id: The request ID (``req_id``) to query.
            req_id: Optional request ID for this call.

        Returns:
            Request-stats dict.
        """
        params: dict[str, Any] = {"obj_id": obj_id}
        if req_id is not None:
            params["req_id"] = req_id
        return (
            await self.client._request("GET", "/request_get_by_id", params=params)
        ).get("data", {})

    async def request_cancel(
        self,
        req_id_to_cancel: str,
        *,
        expire_now: bool = False,
        req_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Cancel a running request.

        The request's status is set to ``canceled`` and any queued tasks
        for it are deleted from Redis.

        Args:
            req_id_to_cancel: The request ID to cancel.
            expire_now: If ``True``, delete the stats entry immediately
                instead of after the default 5-minute grace period.
            req_id: Optional request ID for this call.

        Returns:
            Dict with ``id`` key confirming the cancelled request.
        """
        params: dict[str, Any] = {
            "req_id_to_cancel": req_id_to_cancel,
            "expire_now": expire_now,
        }
        if req_id is not None:
            params["req_id"] = req_id
        return (
            await self.client._request("PATCH", "/request_cancel", params=params)
        ).get("data", {})

    async def request_list(
        self,
        operation_id: str,
        *,
        running_only: bool = False,
        req_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        List all requests for an operation.

        Admins see all requests; regular users see only their own.

        Args:
            operation_id: Operation to filter requests by.
            running_only: If ``True``, return only still-running requests.
            req_id: Optional request ID.

        Returns:
            List of request-stats dicts.
        """
        params: dict[str, Any] = {
            "operation_id": operation_id,
            "running_only": running_only,
        }
        if req_id is not None:
            params["req_id"] = req_id
        return (
            await self.client._request("GET", "/request_list", params=params)
        ).get("data", [])

    async def request_delete(
        self,
        operation_id: str,
        *,
        obj_id: str | None = None,
        req_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Delete one or all requests for an operation.

        Args:
            operation_id: Operation whose requests to delete.
            obj_id: Specific request ID to delete.  If omitted, all
                requests for the operation are deleted.
            req_id: Optional request ID for this call.

        Returns:
            Dict with ``deleted`` count.
        """
        params: dict[str, Any] = {"operation_id": operation_id}
        if obj_id is not None:
            params["obj_id"] = obj_id
        if req_id is not None:
            params["req_id"] = req_id
        return (
            await self.client._request("DELETE", "/request_delete", params=params)
        ).get("data", {})

    # ------------------------------------------------------------------ #
    # Enhance-document map                                                 #
    # ------------------------------------------------------------------ #

    async def enhance_map_create(
        self,
        plugin: str,
        match_criteria: dict[str, Any],
        *,
        glyph_id: str | None = None,
        color: str | None = None,
        req_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Create an enhance-document-map entry.

        Maps a set of key-value criteria on a ``GulpDocument`` (all must
        match, AND semantics) within a plugin to a ``glyph_id`` and/or
        ``color`` for enhanced UI visualization.

        Args:
            plugin: Plugin name the entry applies to (filename without
                extension).
            match_criteria: Dict mapping ``GulpDocument`` field names to
                criteria values. Each value can be:

                - A simple value (string, number, boolean) for exact match
                - A dict with comparison operators for numeric matching:
                  - ``"eq"``: exact equality
                  - ``"gte"``: greater than or equal
                  - ``"lte"``: less than or equal
                  - Operators can be combined (e.g., ``{"gte": 100, "lte": 200}``)

                Example:

                .. code-block:: python

                    {
                        "gulp.event_code": {"eq": 4624},
                        "status": "active",
                        "severity_level": {"gte": 5, "lte": 10},
                    }

            glyph_id: Optional glyph to assign.
            color: Optional CSS hex color string (e.g. ``"#ff0000"``).
            req_id: Optional request ID.

        Returns:
            Created enhance-document-map entry dict.
        """
        params: dict[str, Any] = {"plugin": plugin}
        if glyph_id is not None:
            params["glyph_id"] = glyph_id
        if color is not None:
            params["color"] = color
        if req_id is not None:
            params["req_id"] = req_id
        return (
            await self.client._request(
                "POST", "/enhance_document_map_create", params=params, json=match_criteria
            )
        ).get("data", {})

    async def enhance_map_update(
        self,
        obj_id: str,
        *,
        glyph_id: str | None = None,
        color: str | None = None,
        req_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Update an enhance-document-map entry (glyph and/or color).

        Args:
            obj_id: Entry ID (SHA-1 of ``event_code + plugin``).
            glyph_id: New glyph ID.
            color: New CSS hex color.
            req_id: Optional request ID.

        Returns:
            Updated entry dict.
        """
        params: dict[str, Any] = {"obj_id": obj_id}
        if glyph_id is not None:
            params["glyph_id"] = glyph_id
        if color is not None:
            params["color"] = color
        if req_id is not None:
            params["req_id"] = req_id
        return (
            await self.client._request(
                "PATCH", "/enhance_document_map_update", params=params
            )
        ).get("data", {})

    async def enhance_map_delete(
        self,
        obj_id: str,
        *,
        req_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Delete an enhance-document-map entry.

        Args:
            obj_id: Entry ID.
            req_id: Optional request ID.

        Returns:
            Confirmation dict with ``id`` key.
        """
        params: dict[str, Any] = {"obj_id": obj_id}
        if req_id is not None:
            params["req_id"] = req_id
        return (
            await self.client._request(
                "DELETE", "/enhance_document_map_delete", params=params
            )
        ).get("data", {})

    async def enhance_map_get(
        self,
        obj_id: str,
        *,
        req_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Get an enhance-document-map entry by ID.

        Args:
            obj_id: Entry ID.
            req_id: Optional request ID.

        Returns:
            Entry dict.
        """
        params: dict[str, Any] = {"obj_id": obj_id}
        if req_id is not None:
            params["req_id"] = req_id
        return (
            await self.client._request(
                "GET", "/enhance_document_map_get_by_id", params=params
            )
        ).get("data", {})

    async def enhance_map_list(
        self,
        *,
        flt: dict[str, Any] | None = None,
        req_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        List enhance-document-map entries, optionally filtered.

        Args:
            flt: Optional ``GulpCollabFilter``-compatible dict.  Use ``plugin``
                key to filter by plugin name.
            req_id: Optional request ID.

        Returns:
            List of entry dicts.
        """
        params: dict[str, Any] = {}
        if req_id is not None:
            params["req_id"] = req_id
        return (
            await self.client._request(
                "POST",
                "/enhance_document_map_list",
                params=params or None,
                json=flt or {},
            )
        ).get("data", [])

    # ------------------------------------------------------------------ #
    # Bulk object delete                                                   #
    # ------------------------------------------------------------------ #

    async def object_delete_bulk(
        self,
        operation_id: str,
        obj_type: str,
        flt: dict[str, Any],
        *,
        req_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Bulk-delete collaboration objects of a given type.

        Args:
            operation_id: Operation to scope the delete.
            obj_type: Collab object type string (e.g. ``"note"``).
            flt: ``GulpCollabFilter``-compatible dict to restrict deletion.
            req_id: Optional request ID.

        Returns:
            Dict with ``deleted`` count.
        """
        params: dict[str, Any] = {
            "operation_id": operation_id,
            "obj_type": obj_type,
        }
        if req_id is not None:
            params["req_id"] = req_id
        return (
            await self.client._request(
                "DELETE", "/object_delete_bulk", params=params, json=flt
            )
        ).get("data", {})

    async def request_set_completed(
        self,
        req_id_to_complete: str,
        *,
        failed: bool = False,
        req_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Manually mark a request as done or failed.

        Requires **admin** permission or ownership of the request.

        Args:
            req_id_to_complete: The request ID to mark completed.
            failed: If ``True``, mark as ``failed``; otherwise ``done``.
            req_id: Optional request ID for this call.

        Returns:
            Dict with ``id`` key confirming the updated request.
        """
        params: dict[str, Any] = {
            "req_id_to_cancel": req_id_to_complete,  # server param name is req_id_to_complete
            "failed": failed,
        }
        # Note: server uses req_id_to_complete as the query param name
        params = {
            "req_id_to_complete": req_id_to_complete,
            "failed": failed,
        }
        if req_id is not None:
            params["req_id"] = req_id
        return (
            await self.client._request("PATCH", "/request_set_completed", params=params)
        ).get("data", {})

    # ------------------------------------------------------------------ #
    # Config management                                                    #
    # ------------------------------------------------------------------ #

    async def config_upload(
        self,
        file_path: str,
        *,
        req_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Upload a Gulp configuration file to the server.

        The file is saved as ``$GULP_WORKING_DIR/gulp_cfg.json``.  The server
        must be restarted for the new config to take effect.  Requires
        **admin** permission.

        Args:
            file_path: Local path to the ``gulp_cfg.json`` file.
            req_id: Optional request ID.

        Returns:
            Dict with ``file_path`` key showing where the config was saved.
        """
        params: dict[str, Any] = {}
        if req_id is not None:
            params["req_id"] = req_id
        with open(file_path, "rb") as f:
            files = {"file": ("gulp_cfg.json", f, "application/json")}
            response = await self.client._request(
                "POST", "/config_upload", params=params or None, files=files
            )
        return response.get("data", {})

    async def config_download(
        self,
        output_path: str,
        *,
        req_id: str | None = None,
    ) -> str:
        """
        Download the current Gulp configuration file from the server.

        Requires **admin** permission.

        Args:
            output_path: Local path to save the downloaded ``gulp_cfg.json``.
            req_id: Optional request ID.

        Returns:
            ``output_path`` on success.
        """
        params: dict[str, Any] = {}
        if req_id is not None:
            params["req_id"] = req_id
        req_headers: dict[str, str] = {}
        if self.client.token:
            req_headers["token"] = self.client.token
        resp = await self.client._client.get(
            "/config_download", params=params or None, headers=req_headers
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

