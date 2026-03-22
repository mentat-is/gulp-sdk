"""Collaboration API — notes, links, highlights, glyphs."""

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from gulp_sdk.client import GulpClient


class CollabAPI:
    """Collaboration endpoints."""

    def __init__(self, client: "GulpClient") -> None:
        self.client = client

    # ------------------------------------------------------------------ notes

    async def note_create(
        self,
        operation_id: str,
        context_id: str,
        source_id: str,
        name: str,
        text: str,
        *,
        ws_id: str | None = None,
        tags: list[str] | None = None,
        glyph_id: str | None = None,
        color: str | None = None,
        private: bool | None = None,
        time_pin: int | None = None,
        doc: dict[str, Any] | None = None,
        req_id: str | None = None,
    ) -> dict[str, Any]:
        """Create a collaboration note in a specific operation/context/source."""
        params: dict[str, Any] = {
            "operation_id": operation_id,
            "context_id": context_id,
            "source_id": source_id,
            "ws_id": ws_id or self.client.ws_id,
            "name": name,
        }
        if glyph_id is not None:
            params["glyph_id"] = glyph_id
        if color is not None:
            params["color"] = color
        if private is not None:
            params["private"] = private
        if time_pin is not None:
            params["time_pin"] = time_pin
        if req_id is not None:
            params["req_id"] = req_id

        body: dict[str, Any] = {
            "text": text,
            "tags": tags or [],
        }
        if doc is not None:
            body["doc"] = doc

        response_data = await self.client._request(
            "POST", "/note_create", json=body, params=params
        )
        return response_data.get("data", {})

    async def note_update(
        self,
        obj_id: str,
        *,
        ws_id: str | None = None,
        name: str | None = None,
        text: str | None = None,
        tags: list[str] | None = None,
        glyph_id: str | None = None,
        color: str | None = None,
        doc: dict[str, Any] | None = None,
        time_pin: int | None = None,
        req_id: str | None = None,
    ) -> dict[str, Any]:
        """Update an existing collaboration note by note object ID."""
        params: dict[str, Any] = {
            "obj_id": obj_id,
            "ws_id": ws_id or self.client.ws_id,
        }
        if name is not None:
            params["name"] = name
        if glyph_id is not None:
            params["glyph_id"] = glyph_id
        if color is not None:
            params["color"] = color
        if time_pin is not None:
            params["time_pin"] = time_pin
        if req_id is not None:
            params["req_id"] = req_id

        body: dict[str, Any] = {}
        if text is not None:
            body["text"] = text
        if tags is not None:
            body["tags"] = tags
        if doc is not None:
            body["doc"] = doc

        response_data = await self.client._request(
            "PATCH", "/note_update", json=body or None, params=params
        )
        return response_data.get("data", {})

    async def note_delete(
        self,
        obj_id: str,
        *,
        ws_id: str | None = None,
        req_id: str | None = None,
    ) -> dict[str, Any]:
        """Delete a collaboration note by object ID."""
        params: dict[str, Any] = {"obj_id": obj_id, "ws_id": ws_id or self.client.ws_id}
        if req_id is not None:
            params["req_id"] = req_id
        response_data = await self.client._request("DELETE", "/note_delete", params=params)
        return response_data.get("data", {})

    async def note_get_by_id(
        self,
        obj_id: str,
        *,
        req_id: str | None = None,
    ) -> dict[str, Any]:
        """Retrieve a collaboration note by object ID."""
        params: dict[str, Any] = {"obj_id": obj_id}
        if req_id is not None:
            params["req_id"] = req_id
        response_data = await self.client._request("GET", "/note_get_by_id", params=params)
        return response_data.get("data", {})

    async def note_list(
        self,
        *,
        operation_id: str | None = None,
        flt: dict[str, Any] | None = None,
        req_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """List collaboration notes for an operation or filter."""
        params: dict[str, Any] = {}
        if operation_id is None and flt:
            op_ids = flt.get("operation_ids")
            if isinstance(op_ids, list) and op_ids:
                operation_id = op_ids[0]
        if operation_id is not None:
            params["operation_id"] = operation_id
        if req_id is not None:
            params["req_id"] = req_id
        response_data = await self.client._request(
            "POST", "/note_list", json=flt or {}, params=params or None
        )
        return response_data.get("data", [])

    # ------------------------------------------------------------------ links

    async def link_create(
        self,
        operation_id: str,
        doc_id_from: str,
        doc_ids: list[str],
        *,
        ws_id: str | None = None,
        name: str | None = None,
        description: str | None = None,
        tags: list[str] | None = None,
        glyph_id: str | None = None,
        color: str | None = None,
        private: bool | None = None,
        req_id: str | None = None,
    ) -> dict[str, Any]:
        """Create a document link in collaboration context."""
        params: dict[str, Any] = {
            "operation_id": operation_id,
            "doc_id_from": doc_id_from,
            "ws_id": ws_id or self.client.ws_id,
        }
        if name is not None:
            params["name"] = name
        if glyph_id is not None:
            params["glyph_id"] = glyph_id
        if color is not None:
            params["color"] = color
        if private is not None:
            params["private"] = private
        if req_id is not None:
            params["req_id"] = req_id

        body: dict[str, Any] = {
            "doc_ids": doc_ids,
            "description": description or "",
            "tags": tags or [],
        }
        response_data = await self.client._request(
            "POST", "/link_create", json=body, params=params
        )
        return response_data.get("data", {})

    async def link_update(
        self,
        obj_id: str,
        *,
        ws_id: str | None = None,
        name: str | None = None,
        description: str | None = None,
        tags: list[str] | None = None,
        glyph_id: str | None = None,
        color: str | None = None,
        doc_ids: list[str] | None = None,
        req_id: str | None = None,
    ) -> dict[str, Any]:
        """Update an existing link object by obj_id."""
        params: dict[str, Any] = {"obj_id": obj_id, "ws_id": ws_id or self.client.ws_id}
        if name is not None:
            params["name"] = name
        if glyph_id is not None:
            params["glyph_id"] = glyph_id
        if color is not None:
            params["color"] = color
        if req_id is not None:
            params["req_id"] = req_id

        body: dict[str, Any] = {
            "doc_ids": doc_ids or [],
            "description": description or "",
            "tags": tags or [],
        }
        response_data = await self.client._request(
            "PATCH", "/link_update", json=body, params=params
        )
        return response_data.get("data", {})

    async def link_delete(
        self,
        obj_id: str,
        *,
        ws_id: str | None = None,
        req_id: str | None = None,
    ) -> dict[str, Any]:
        """Delete a link by object ID."""
        params: dict[str, Any] = {"obj_id": obj_id, "ws_id": ws_id or self.client.ws_id}
        if req_id is not None:
            params["req_id"] = req_id
        response_data = await self.client._request("DELETE", "/link_delete", params=params)
        return response_data.get("data", {})

    async def link_get_by_id(
        self,
        obj_id: str,
        *,
        req_id: str | None = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {"obj_id": obj_id}
        if req_id is not None:
            params["req_id"] = req_id
        response_data = await self.client._request("GET", "/link_get_by_id", params=params)
        return response_data.get("data", {})

    async def link_list(
        self,
        *,
        operation_id: str | None = None,
        flt: dict[str, Any] | None = None,
        req_id: str | None = None,
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {}
        if operation_id is None and flt:
            op_ids = flt.get("operation_ids")
            if isinstance(op_ids, list) and op_ids:
                operation_id = op_ids[0]
        if operation_id is not None:
            params["operation_id"] = operation_id
        if req_id is not None:
            params["req_id"] = req_id
        response_data = await self.client._request(
            "POST", "/link_list", json=flt or {}, params=params or None
        )
        return response_data.get("data", [])

    # --------------------------------------------------------------- highlights

    async def highlight_create(
        self,
        operation_id: str,
        time_range: tuple[int, int] | list[int],
        *,
        ws_id: str | None = None,
        name: str | None = None,
        description: str | None = None,
        tags: list[str] | None = None,
        glyph_id: str | None = None,
        color: str | None = None,
        private: bool = False,
        req_id: str | None = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {
            "operation_id": operation_id,
            "ws_id": ws_id or self.client.ws_id,
            "private": private,
        }
        if name is not None:
            params["name"] = name
        if glyph_id is not None:
            params["glyph_id"] = glyph_id
        if color is not None:
            params["color"] = color
        if req_id is not None:
            params["req_id"] = req_id

        body: dict[str, Any] = {
            "time_range": list(time_range),
            "description": description or "",
            "tags": tags or [],
        }
        response_data = await self.client._request(
            "POST", "/highlight_create", json=body, params=params
        )
        return response_data.get("data", {})

    async def highlight_update(
        self,
        obj_id: str,
        *,
        ws_id: str | None = None,
        name: str | None = None,
        description: str | None = None,
        tags: list[str] | None = None,
        glyph_id: str | None = None,
        color: str | None = None,
        time_range: tuple[int, int] | list[int] | None = None,
        req_id: str | None = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {"obj_id": obj_id, "ws_id": ws_id or self.client.ws_id}
        if name is not None:
            params["name"] = name
        if glyph_id is not None:
            params["glyph_id"] = glyph_id
        if color is not None:
            params["color"] = color
        if req_id is not None:
            params["req_id"] = req_id

        body: dict[str, Any] = {
            "time_range": list(time_range) if time_range is not None else [],
            "description": description or "",
            "tags": tags or [],
        }
        response_data = await self.client._request(
            "PATCH", "/highlight_update", json=body, params=params
        )
        return response_data.get("data", {})

    async def highlight_delete(
        self,
        obj_id: str,
        *,
        ws_id: str | None = None,
        req_id: str | None = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {"obj_id": obj_id, "ws_id": ws_id or self.client.ws_id}
        if req_id is not None:
            params["req_id"] = req_id
        response_data = await self.client._request(
            "DELETE", "/highlight_delete", params=params
        )
        return response_data.get("data", {})

    async def highlight_get_by_id(
        self,
        obj_id: str,
        *,
        req_id: str | None = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {"obj_id": obj_id}
        if req_id is not None:
            params["req_id"] = req_id
        response_data = await self.client._request(
            "GET", "/highlight_get_by_id", params=params
        )
        return response_data.get("data", {})

    async def highlight_list(
        self,
        *,
        operation_id: str | None = None,
        flt: dict[str, Any] | None = None,
        req_id: str | None = None,
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {}
        if operation_id is None and flt:
            op_ids = flt.get("operation_ids")
            if isinstance(op_ids, list) and op_ids:
                operation_id = op_ids[0]
        if operation_id is not None:
            params["operation_id"] = operation_id
        if req_id is not None:
            params["req_id"] = req_id
        response_data = await self.client._request(
            "POST", "/highlight_list", json=flt or {}, params=params or None
        )
        return response_data.get("data", [])

    # ------------------------------------------------------------------ glyphs

    async def glyph_create(
        self,
        img_path: str,
        *,
        name: str | None = None,
        private: bool | None = None,
        req_id: str | None = None,
    ) -> dict[str, Any]:
        import pathlib

        p = pathlib.Path(img_path)
        img_bytes = p.read_bytes()
        files = [("img", (p.name, img_bytes, "application/octet-stream"))]
        params: dict[str, Any] = {}
        if name is not None:
            params["name"] = name
        if private is not None:
            params["private"] = private
        if req_id is not None:
            params["req_id"] = req_id
        response_data = await self.client._request(
            "POST", "/glyph_create", files=files, params=params or None
        )
        return response_data.get("data", {})

    async def glyph_update(
        self,
        obj_id: str,
        *,
        name: str | None = None,
        img_path: str | None = None,
        req_id: str | None = None,
    ) -> dict[str, Any]:
        import pathlib

        params: dict[str, Any] = {"obj_id": obj_id}
        if name is not None:
            params["name"] = name
        if req_id is not None:
            params["req_id"] = req_id

        files = None
        if img_path is not None:
            p = pathlib.Path(img_path)
            img_bytes = p.read_bytes()
            files = [("img", (p.name, img_bytes, "application/octet-stream"))]

        response_data = await self.client._request(
            "PATCH", "/glyph_update", files=files, params=params
        )
        return response_data.get("data", {})

    async def glyph_delete(
        self,
        obj_id: str,
        *,
        req_id: str | None = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {"obj_id": obj_id}
        if req_id is not None:
            params["req_id"] = req_id
        response_data = await self.client._request("DELETE", "/glyph_delete", params=params)
        return response_data.get("data", {})

    async def glyph_get_by_id(
        self,
        obj_id: str,
        *,
        req_id: str | None = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {"obj_id": obj_id}
        if req_id is not None:
            params["req_id"] = req_id
        response_data = await self.client._request("GET", "/glyph_get_by_id", params=params)
        return response_data.get("data", {})

    async def glyph_list(
        self,
        *,
        flt: dict[str, Any] | None = None,
        req_id: str | None = None,
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {}
        if req_id is not None:
            params["req_id"] = req_id
        response_data = await self.client._request(
            "POST", "/glyph_list", json=flt or {}, params=params or None
        )
        return response_data.get("data", [])
