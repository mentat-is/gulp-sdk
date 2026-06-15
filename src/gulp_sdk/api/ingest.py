"""
Ingestion API — file/raw/zip ingestion, preview, status.
"""

from typing import TYPE_CHECKING, Any, Callable
from pathlib import Path
import json
import uuid
from pydantic import BaseModel, ConfigDict

from gulp_sdk.api.request_utils import wait_for_request_stats
from gulp_sdk.exceptions import GulpSDKError

if TYPE_CHECKING:
    from gulp_sdk.client import GulpClient
    from gulp_sdk.websocket import WSMessage


class IngestResult(BaseModel):
    """Result of ingestion operation."""

    model_config = ConfigDict(extra="allow")

    req_id: str
    status: str

class IngestAPI:
    """Ingestion endpoints."""

    def __init__(self, client: "GulpClient") -> None:
        """Initialize with client reference."""
        self.client = client

    @staticmethod
    def _coerce_raw_bytes(data: dict[str, Any] | list[Any] | str | bytes) -> bytes:
        """Convert raw ingestion payload into the bytes chunk expected by the backend."""
        if isinstance(data, bytes):
            return data
        if isinstance(data, str):
            return data.encode("utf-8")
        return json.dumps(data).encode("utf-8")

    async def _upload_multipart_file(
        self,
        path: str,
        file_path: Path,
        payload: dict[str, Any],
        params: dict[str, Any],
        content_type: str,
    ) -> dict[str, Any]:
        """Upload a file using the backend resume protocol."""
        total_size = file_path.stat().st_size
        continue_offset = 0
        request_params = dict(params)
        request_params.setdefault("req_id", str(uuid.uuid4()))

        while True:
            with file_path.open("rb") as f:
                f.seek(continue_offset)
                file_bytes = f.read()

            response_data = await self.client._request(
                "POST",
                path,
                files=[
                    ("payload", ("payload.json", json.dumps(payload), "application/json")),
                    ("f", (file_path.name, file_bytes, content_type)),
                ],
                headers={
                    "size": str(total_size),
                    "continue_offset": str(continue_offset),
                },
                params=request_params,
            )

            data = response_data.get("data", {})
            if not isinstance(data, dict) or data.get("done") is not False:
                return response_data

            try:
                next_offset = int(data["continue_offset"])
            except (KeyError, TypeError, ValueError) as ex:
                raise GulpSDKError(
                    f"Invalid upload resume response: {response_data}"
                ) from ex

            if next_offset <= continue_offset or next_offset > total_size:
                raise GulpSDKError(
                    f"Invalid upload resume offset {next_offset} for file size {total_size}"
                )

            continue_offset = next_offset
            if response_data.get("req_id"):
                request_params["req_id"] = response_data["req_id"]

    async def file(
        self,
        operation_id: str,
        plugin_name: str,
        file_path: str,
        context_name: str = "sdk_context",
        ws_id: str | None = None,
        params: dict[str, Any] | None = None,
        wait: bool = False,
        timeout: int = 120,
        ws_callback: "Callable[[WSMessage], None] | None" = None,
    ) -> IngestResult:
        """
        Ingest a file using specified plugin.

        Args:
            operation_id: Operation ID
            plugin_name: Plugin name (e.g., "json", "evtx")
            file_path: Path to file to ingest
            context_name: Context name used by Gulp for source grouping
            ws_id: Websocket id for async progress notifications
            params: Optional plugin-specific parameters

        Returns:
            IngestResult with req_id for status tracking
        """
        file_path_obj = Path(file_path)

        payload: dict[str, Any] = {
            "flt": {},
            "plugin_params": {},
            "original_file_path": str(file_path_obj),
        }
        if params:
            payload.update(params)
        request_params = {
            "operation_id": operation_id,
            "context_name": context_name,
            "plugin": plugin_name,
            "ws_id": ws_id or self.client.ws_id,
        }
        if "req_id" in payload:
            request_params["req_id"] = payload.pop("req_id")

        response_data = await self._upload_multipart_file(
            "/ingest_file",
            file_path_obj,
            payload,
            request_params,
            "application/octet-stream",
        )

        result_data = response_data.get("data", {})
        result = IngestResult.model_validate(
            {
                "req_id": response_data.get("req_id", ""),
                "status": response_data.get("status", "pending"),
                **(result_data if isinstance(result_data, dict) else {}),
            }
        )

        if wait and result.status == "pending" and result.req_id:
            stats = await wait_for_request_stats(self.client, result.req_id, timeout, ws_callback=ws_callback)
            if isinstance(stats, dict):
                return IngestResult.model_validate(
                    {
                        "req_id": result.req_id,
                        "status": str(stats.get("status", result.status)),
                    }
                )

        return result

    async def raw(
        self,
        operation_id: str,
        plugin_name: str,
        data: dict[str, Any] | str | bytes,
        params: dict[str, Any] | None = None,
        wait: bool = False,
        timeout: int = 120,
        ws_callback: "Callable[[WSMessage], None] | None" = None,
    ) -> IngestResult:
        """
        Ingest raw data using specified plugin.

        Args:
            operation_id: Operation ID
            plugin_name: Plugin name
            data: Raw data (dict, string, or bytes)
            params: Optional plugin-specific parameters

        Returns:
            IngestResult with req_id for status tracking
        """
        payload: dict[str, Any] = {
            "flt": {},
            "plugin_params": {},
        }
        request_params: dict[str, Any] = {
            "operation_id": operation_id,
            "ws_id": self.client.ws_id,
        }
        if plugin_name:
            request_params["plugin"] = plugin_name
        if params:
            if "flt" in params:
                payload["flt"] = params["flt"]
            if "plugin_params" in params:
                payload["plugin_params"] = params["plugin_params"]
            if "last" in params:
                request_params["last"] = params["last"]
            if "req_id" in params:
                request_params["req_id"] = params["req_id"]
            if "ws_id" in params:
                request_params["ws_id"] = params["ws_id"]

        files = [
            ("payload", ("payload.json", json.dumps(payload), "application/json")),
            (
                "f",
                (
                    "chunk",
                    self._coerce_raw_bytes(data),
                    "application/octet-stream",
                ),
            ),
        ]

        response_data = await self.client._request(
            "POST",
            "/ingest_raw",
            files=files,
            params=request_params,
        )

        result_data = response_data.get("data", {})
        result = IngestResult.model_validate(
            {
                "req_id": response_data.get("req_id", ""),
                "status": response_data.get("status", "pending"),
                **(result_data if isinstance(result_data, dict) else {}),
            }
        )

        if wait and result.status == "pending" and result.req_id:
            stats = await wait_for_request_stats(self.client, result.req_id, timeout, ws_callback=ws_callback)
            if isinstance(stats, dict):
                return IngestResult.model_validate(
                    {
                        "req_id": result.req_id,
                        "status": str(stats.get("status", result.status)),
                    }
                )

        return result

    async def zip(
        self,
        operation_id: str,
        plugin_name: str,
        zipfile_path: str,
        params: dict[str, Any] | None = None,
        wait: bool = False,
        timeout: int = 120,
        ws_callback: "Callable[[WSMessage], None] | None" = None,
    ) -> IngestResult:
        """
        Ingest ZIP archive using specified plugin.

        Args:
            operation_id: Operation ID
            plugin_name: Plugin name
            zipfile_path: Path to .zip file
            params: Optional plugin-specific parameters

        Returns:
            IngestResult with req_id for status tracking
        """
        zip_path_obj = Path(zipfile_path)

        # ingest_zip uses the same multipart chunked upload pattern as ingest_file.
        payload: dict[str, Any] = {"flt": {}}
        if params:
            payload.update(params)

        # NOTE: plugin_name is kept for backward compatibility with SDK callers,
        # but the /ingest_zip endpoint resolves plugins from metadata.json in the zip.
        request_params = {
            "operation_id": operation_id,
            "context_name": "sdk_context",
            "ws_id": self.client.ws_id,
        }
        if "req_id" in payload:
            request_params["req_id"] = payload.pop("req_id")

        response_data = await self._upload_multipart_file(
            "/ingest_zip",
            zip_path_obj,
            payload,
            request_params,
            "application/zip",
        )

        result_data = response_data.get("data", {})
        result = IngestResult.model_validate(
            {
                "req_id": response_data.get("req_id", ""),
                "status": response_data.get("status", "pending"),
                **(result_data if isinstance(result_data, dict) else {}),
            }
        )

        if wait and result.status == "pending" and result.req_id:
            stats = await wait_for_request_stats(self.client, result.req_id, timeout, ws_callback=ws_callback)
            if isinstance(stats, dict):
                return IngestResult.model_validate(
                    {
                        "req_id": result.req_id,
                        "status": str(stats.get("status", result.status)),
                    }
                )

        return result

    async def preview(
        self,
        operation_id: str,
        plugin_name: str,
        file_path: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Preview ingestion result without actually ingesting.

        Args:
            operation_id: Operation ID
            plugin_name: Plugin name
            file_path: Path to file
            params: Optional plugin-specific parameters

        Returns:
            Preview data (sample documents, errors, etc.)
        """
        file_path_obj = Path(file_path)

        request_params: dict[str, Any] = {
            "operation_id": operation_id,
            "context_name": "sdk_context",
            "plugin": plugin_name,
            "preview_mode": True,
            "ws_id": self.client.ws_id,
        }
        payload: dict[str, Any] = {
            "flt": {},
            "plugin_params": {"preview_mode": True},
            "original_file_path": str(file_path_obj),
        }
        if params:
            if "context_name" in params:
                request_params["context_name"] = params["context_name"]
            if "ws_id" in params:
                request_params["ws_id"] = params["ws_id"]
            if "req_id" in params:
                request_params["req_id"] = params["req_id"]
            if "flt" in params:
                payload["flt"] = params["flt"]
            if "plugin_params" in params:
                plugin_params = dict(params["plugin_params"])
                plugin_params["preview_mode"] = True
                payload["plugin_params"] = plugin_params

        response_data = await self._upload_multipart_file(
            "/ingest_file",
            file_path_obj,
            payload,
            request_params,
            "application/octet-stream",
        )

        return response_data.get("data", {})

    async def status(
        self,
        operation_id: str,
        req_id: str,
    ) -> dict[str, Any]:
        """
        Get ingestion status by request ID.

        Args:
            operation_id: Operation ID
            req_id: Ingestion request ID (from ingest* method result)

        Returns:
            Status dictionary with progress, errors, etc.
        """
        response_data = await self.client._request(
            "GET",
            "/request_get_by_id",
            params={"obj_id": req_id},
        )

        return response_data.get("data", {})

    async def file_to_source(
        self,
        source_id: str,
        file_path: str,
        *,
        plugin_params: dict[str, Any] | None = None,
        flt: dict[str, Any] | None = None,
        ws_id: str | None = None,
        req_id: str | None = None,
        wait: bool = False,
        timeout: int = 120,
        ws_callback: "Callable[[WSMessage], None] | None" = None,
    ) -> IngestResult:
        """
        Ingest a file into an existing source.

        The operation is derived from the source itself.  If the source has
        associated plugin parameters, they are used unless overridden via
        ``payload``.

        Args:
            source_id: Target source ID.
            file_path: Local path to the file to ingest.
            plugin_params: Override plugin parameters (``GulpPluginParameters`` dict).
            flt: ``GulpIngestionFilter`` dict.
            ws_id: WebSocket ID for progress notifications.
            req_id: Optional request ID.
            wait: If True, wait for async completion and return final request status.
            timeout: Max seconds to wait if ``wait`` is True (0 for no timeout).

        Returns:
            ``IngestResult`` with ``req_id`` for tracking.
        """
        file_path_obj = Path(file_path)

        payload: dict[str, Any] = {
            "flt": flt or {},
            "plugin_params": plugin_params or {},
            "original_file_path": str(file_path_obj),
        }

        params: dict[str, Any] = {
            "source_id": source_id,
            "ws_id": ws_id or self.client.ws_id,
        }
        if req_id is not None:
            params["req_id"] = req_id

        response_data = await self._upload_multipart_file(
            "/ingest_file_to_source",
            file_path_obj,
            payload,
            params,
            "application/octet-stream",
        )
        result = IngestResult.model_validate(
            {
                "req_id": response_data.get("req_id", ""),
                "status": response_data.get("status", "pending"),
                **(response_data.get("data", {}) or {}),
            }
        )

        if wait and result.status == "pending" and result.req_id:
            stats = await wait_for_request_stats(self.client, result.req_id, timeout, ws_callback=ws_callback)
            if isinstance(stats, dict):
                # Only return stable, validated fields to avoid validation errors
                # when the backend returns unexpected types in stats.
                return IngestResult.model_validate(
                    {
                        "req_id": result.req_id,
                        "status": str(stats.get("status", result.status)),
                    }
                )

        return result

    async def file_local(
        self,
        operation_id: str,
        context_name: str,
        plugin: str,
        path: str,
        *,
        ws_id: str | None = None,
        plugin_params: dict[str, Any] | None = None,
        flt: dict[str, Any] | None = None,
        delete_after: bool = False,
        req_id: str | None = None,
        wait: bool = False,
        timeout: int = 120,
        ws_callback: "Callable[[WSMessage], None] | None" = None,
    ) -> IngestResult:
        """
        Ingest a file that already resides on the server's local storage.

        The ``path`` must be relative to ``$GULP_WORKING_DIR/ingest_local``
        on the server.  Requires **ingest** permission.

        Args:
            operation_id: Target operation.
            context_name: Context name for the ingestion.
            plugin: Plugin name (e.g. ``"win_evtx"``).
            path: Server-side path relative to ``ingest_local``.
            ws_id: WebSocket ID.
            plugin_params: ``GulpPluginParameters`` dict.
            flt: ``GulpIngestionFilter`` dict.
            delete_after: Delete the file from the server after processing.
            req_id: Optional request ID.

        Returns:
            ``IngestResult`` with ``req_id`` for tracking.
        """
        params: dict[str, Any] = {
            "operation_id": operation_id,
            "context_name": context_name,
            "plugin": plugin,
            "path": path,
            "ws_id": ws_id or self.client.ws_id,
            "delete_after": delete_after,
        }
        if req_id is not None:
            params["req_id"] = req_id
        if plugin_params is not None:
            params["plugin_params"] = json.dumps(plugin_params)
        if flt is not None:
            params["flt"] = json.dumps(flt)

        response_data = await self.client._request(
            "POST", "/ingest_file_local", params=params
        )
        result = IngestResult.model_validate(
            {
                "req_id": response_data.get("req_id", ""),
                "status": response_data.get("status", "pending"),
                **(response_data.get("data", {}) or {}),
            }
        )

        if wait and result.status == "pending" and result.req_id:
            stats = await wait_for_request_stats(self.client, result.req_id, timeout, ws_callback=ws_callback)
            if isinstance(stats, dict):
                return IngestResult.model_validate(
                    {
                        "req_id": result.req_id,
                        "status": str(stats.get("status", result.status)),
                    }
                )

        return result

    async def file_local_to_source(
        self,
        source_id: str,
        path: str,
        *,
        ws_id: str | None = None,
        plugin_params: dict[str, Any] | None = None,
        flt: dict[str, Any] | None = None,
        delete_after: bool = False,
        req_id: str | None = None,
        wait: bool = False,
        timeout: int = 120,
        ws_callback: "Callable[[WSMessage], None] | None" = None,
    ) -> IngestResult:
        """
        Ingest a server-local file into an existing source.

        Combines :meth:`file_to_source` with local-file convenience.  The
        ``path`` must be relative to ``$GULP_WORKING_DIR/ingest_local``.

        Args:
            source_id: Target source ID.
            path: Server-side path relative to ``ingest_local``.
            ws_id: WebSocket ID.
            plugin_params: Override plugin parameters (``GulpPluginParameters`` dict).
            flt: ``GulpIngestionFilter`` dict.
            delete_after: Delete the file from the server after processing.
            req_id: Optional request ID.

        Returns:
            ``IngestResult`` with ``req_id`` for tracking.
        """
        params: dict[str, Any] = {
            "source_id": source_id,
            "path": path,
            "ws_id": ws_id or self.client.ws_id,
            "delete_after": delete_after,
        }
        if req_id is not None:
            params["req_id"] = req_id

        body: dict[str, Any] = {}
        if plugin_params is not None:
            body["plugin_params"] = plugin_params
        if flt is not None:
            body["flt"] = flt

        response_data = await self.client._request(
            "POST",
            "/ingest_file_local_to_source",
            params=params,
            json=body or None,
        )
        result = IngestResult.model_validate(
            {
                "req_id": response_data.get("req_id", ""),
                "status": response_data.get("status", "pending"),
                **(response_data.get("data", {}) or {}),
            }
        )

        if wait and result.status == "pending" and result.req_id:
            stats = await wait_for_request_stats(self.client, result.req_id, timeout, ws_callback=ws_callback)
            if isinstance(stats, dict):
                return IngestResult.model_validate(
                    {
                        "req_id": result.req_id,
                        "status": str(stats.get("status", result.status)),
                    }
                )

        return result

    async def zip_local(
        self,
        operation_id: str,
        context_name: str,
        path: str,
        *,
        ws_id: str | None = None,
        flt: dict[str, Any] | None = None,
        delete_after: bool = False,
        req_id: str | None = None,
        wait: bool = False,
        timeout: int = 120,
        ws_callback: "Callable[[WSMessage], None] | None" = None,
    ) -> IngestResult:
        """
        Ingest a ZIP archive that resides on the server's local storage.

        The ``path`` must be relative to ``$GULP_WORKING_DIR/ingest_local``.
        The ZIP must contain a ``metadata.json`` (array of
        ``GulpZipMetadataEntry``).

        Args:
            operation_id: Target operation.
            context_name: Context name for the ingestion.
            path: Server-side path relative to ``ingest_local``.
            ws_id: WebSocket ID.
            flt: ``GulpIngestionFilter`` dict applied to all files.
            delete_after: Delete the ZIP after processing.
            req_id: Optional request ID.

        Returns:
            ``IngestResult`` with ``req_id`` for tracking.
        """
        params: dict[str, Any] = {
            "operation_id": operation_id,
            "context_name": context_name,
            "path": path,
            "ws_id": ws_id or self.client.ws_id,
            "delete_after": delete_after,
        }
        if req_id is not None:
            params["req_id"] = req_id
        if flt is not None:
            params["flt"] = json.dumps(flt)

        response_data = await self.client._request(
            "POST", "/ingest_zip_local", params=params
        )
        result = IngestResult.model_validate(
            {
                "req_id": response_data.get("req_id", ""),
                "status": response_data.get("status", "pending"),
                **(response_data.get("data", {}) or {}),
            }
        )

        if wait and result.status == "pending" and result.req_id:
            stats = await wait_for_request_stats(self.client, result.req_id, timeout, ws_callback=ws_callback)
            if isinstance(stats, dict):
                return IngestResult.model_validate(
                    {
                        "req_id": result.req_id,
                        "status": str(stats.get("status", result.status)),
                    }
                )

        return result

    async def local_list(
        self,
        *,
        req_id: str | None = None,
    ) -> list[str]:
        """
        List files available in the server's ``ingest_local`` directory.

        Returned paths are relative to ``$GULP_WORKING_DIR/ingest_local``.
        Requires **ingest** permission.

        Args:
            req_id: Optional request ID.

        Returns:
            List of relative file paths.
        """
        params: dict[str, Any] = {}
        if req_id is not None:
            params["req_id"] = req_id
        response_data = await self.client._request(
            "GET", "/ingest_local_list", params=params or None
        )
        return response_data.get("data", [])
