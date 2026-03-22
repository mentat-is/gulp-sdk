"""
Documents API — this module is a compatibility shim.

The original implementation used endpoints (``/operations/{id}/documents``)
that do not exist in the Gulp server.  Document querying is fully handled by
the :class:`~gulp_sdk.api.queries.QueriesAPI` module (``client.queries``).

Use ``client.queries.query_gulp()``, ``client.queries.query_raw()``, or
``client.queries.query_single_id()`` instead.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from gulp_sdk.client import GulpClient


class DocumentsAPI:
    """
    Compatibility shim — document operations are part of QueriesAPI.

    All methods raise ``NotImplementedError`` with a migration hint.
    Use ``client.queries`` instead.
    """

    def __init__(self, client: "GulpClient") -> None:
        self.client = client

    def __getattr__(self, name: str):  # type: ignore[override]
        raise NotImplementedError(
            f"DocumentsAPI.{name}() is not implemented. "
            "Use client.queries.query_gulp(), client.queries.query_raw(), "
            "or client.queries.query_single_id() instead."
        )
