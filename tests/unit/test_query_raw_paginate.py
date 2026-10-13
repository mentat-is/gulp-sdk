"""Focused tests for raw offset and PIT pagination wrappers."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from gulp_sdk.api.queries import QueriesAPI


@pytest.mark.unit
async def test_query_raw_paginate_preserves_legacy_offset_options() -> None:
    client = SimpleNamespace(
        _request=AsyncMock(
            return_value={
                "status": "success",
                "data": {"total_hits": 1, "docs": [{"_id": "doc-1"}]},
            }
        )
    )
    api = QueriesAPI(client)

    result = await api.query_raw_paginate(
        "op-1",
        {"query": {"match_all": {}}},
        {"limit": 50, "offset": 10},
        req_id="req-1",
    )

    assert result == {"total_hits": 1, "docs": [{"_id": "doc-1"}]}
    client._request.assert_awaited_once_with(
        "POST",
        "/query_raw_paginate",
        json={
            "q": {"query": {"match_all": {}}},
            "q_options": {"limit": 50, "offset": 10},
        },
        params={"operation_id": "op-1", "req_id": "req-1"},
    )


@pytest.mark.unit
async def test_query_raw_paginate_serializes_pit_and_scalar_cursor() -> None:
    client = SimpleNamespace(
        _request=AsyncMock(
            return_value={
                "status": "success",
                "data": {
                    "total_hits": 20_000,
                    "docs": [],
                    "pit_id": "pit-next",
                    "search_after": [1_725_000_000_000, "shard-42"],
                },
            }
        )
    )
    api = QueriesAPI(client)

    result = await api.query_raw_paginate(
        "op-1",
        {"query": {"match_all": {}}},
        {"limit": 100, "offset": 12_000, "sort": {"@timestamp": "asc"}},
        pagination_mode="pit",
        pit_id="pit-current",
        search_after=[1_724_999_999_999, "shard-41"],
    )

    assert result["pit_id"] == "pit-next"
    assert result["search_after"] == [1_725_000_000_000, "shard-42"]
    call = client._request.await_args
    assert call.kwargs["json"]["q_options"] == {
        "limit": 100,
        "offset": 12_000,
        "sort": {"@timestamp": "asc"},
        "pagination_mode": "pit",
        "pit_id": "pit-current",
        "search_after": [1_724_999_999_999, "shard-41"],
    }


@pytest.mark.unit
async def test_query_raw_paginate_close_sends_pit_in_delete_body() -> None:
    client = SimpleNamespace(
        _request=AsyncMock(return_value={"status": "success", "data": {"closed": True}})
    )
    api = QueriesAPI(client)

    result = await api.query_raw_paginate_close("op-1", "pit-to-close", req_id="req-close")

    assert result == {"closed": True}
    client._request.assert_awaited_once_with(
        "DELETE",
        "/query_raw_paginate",
        json={"pit_id": "pit-to-close"},
        params={"operation_id": "op-1", "req_id": "req-close"},
    )
