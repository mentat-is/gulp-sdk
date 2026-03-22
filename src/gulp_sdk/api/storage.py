"""
Storage API — manage files on the S3-compatible file store.

Quick example::

    async with GulpClient("http://localhost:8080") as client:
        await client.auth.login("user", "pass")

        # List files for an operation
        files = await client.storage.list_files(operation_id="my_op")

        # Delete a specific file
        await client.storage.delete_by_id(
            operation_id="my_op",
            storage_id="my_op/ctx/src/logfile.evtx",
        )
"""

import inspect
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from gulp_sdk.client import GulpClient


class StorageAPI:
    """
    Storage (S3-compatible filestore) endpoints.

    Requires **edit** permission for write operations.
    """

    def __init__(self, client: "GulpClient") -> None:
        self.client = client

    async def delete_by_id(
        self,
        operation_id: str,
        storage_id: str,
        *,
        req_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Delete a file by its storage ID.

        Args:
            operation_id: Parent operation (for permission check).
            storage_id: Storage ID of the file (``gulp.storage_id`` field).
            req_id: Optional request ID.

        Returns:
            Confirmation dict.
        """
        params: dict[str, Any] = {"operation_id": operation_id, "storage_id": storage_id}
        if req_id is not None:
            params["req_id"] = req_id
        response_data = await self.client._request(
            "DELETE", "/storage_delete_by_id", params=params
        )
        return response_data.get("data", {})

    async def delete_by_tags(
        self,
        *,
        operation_id: str | None = None,
        context_id: str | None = None,
        req_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Delete all files matching the given operation / context tags.

        Args:
            operation_id: Filter by operation ID.
            context_id: Filter by context ID.
            req_id: Optional request ID.

        Returns:
            Confirmation dict.
        """
        params: dict[str, Any] = {}
        if operation_id is not None:
            params["operation_id"] = operation_id
        if context_id is not None:
            params["context_id"] = context_id
        if req_id is not None:
            params["req_id"] = req_id
        response_data = await self.client._request(
            "DELETE", "/storage_delete_by_tags", params=params or None
        )
        return response_data.get("data", {})

    async def list_files(
        self,
        *,
        operation_id: str | None = None,
        context_id: str | None = None,
        continuation_token: str | None = None,
        max_results: int = 100,
        req_id: str | None = None,
    ) -> dict[str, Any]:
        """
        List files in the file store.

        Results may be paginated.  If the returned dict contains a
        ``continuation_token`` key, pass it in the next call to get the next
        page.

        Args:
            operation_id: Filter by operation ID.
            context_id: Filter by context ID.
            continuation_token: Pagination token from previous call.
            max_results: Maximum files to return (default 100, max 1000).
            req_id: Optional request ID.

        Returns:
            Dict with ``files`` list and optional ``continuation_token``.
        """
        params: dict[str, Any] = {"max_results": max_results}
        if operation_id is not None:
            params["operation_id"] = operation_id
        if context_id is not None:
            params["context_id"] = context_id
        if continuation_token is not None:
            params["continuation_token"] = continuation_token
        if req_id is not None:
            params["req_id"] = req_id
        response_data = await self.client._request(
            "GET", "/storage_list_files", params=params
        )
        return response_data.get("data", {})

    async def get_file_by_id(
        self,
        operation_id: str,
        storage_id: str,
        output_path: str,
        *,
        req_id: str | None = None,
    ) -> str:
        """
        Download a file from storage by its storage ID.

        Args:
            operation_id: Parent operation ID (for permission check).
            storage_id: Storage ID of the file (``gulp.storage_id`` field).
            output_path: Local path to write the downloaded file.
            req_id: Optional request ID.

        Returns:
            ``output_path`` on success.
        """
        params: dict[str, Any] = {
            "operation_id": operation_id,
            "storage_id": storage_id,
        }
        if req_id is not None:
            params["req_id"] = req_id
        # Use raw httpx client for binary download
        req_headers: dict[str, str] = {}
        if self.client.token:
            req_headers["token"] = self.client.token
        resp = await self.client._client.get(
            "/storage_get_file_by_id", params=params, headers=req_headers
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
