"""Unit tests for pagination helpers."""

import pytest
from gulp_sdk.pagination import AsyncPaginator, CursorPaginator


@pytest.mark.unit
async def test_async_paginator_offset_based():
    """Test offset-based pagination."""
    # Mock fetch function
    pages = [
        ([1, 2, 3], 10),  # First page: 3 items, total 10
        ([4, 5, 6], 10),  # Second page
        ([7, 8, 9], 10),  # Third page
        ([10], 10),       # Fourth page: 1 item
    ]
    page_iter = iter(pages)
    
    async def fetch(page_size, offset):
        return next(page_iter)
    
    items = []
    paginator = AsyncPaginator(fetch, page_size=3)
    async for item in paginator:
        items.append(item)
        if len(items) >= 10:
            break
    
    assert items == [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]


@pytest.mark.unit
async def test_cursor_paginator():
    """Test cursor-based pagination."""
    pages = [
        ([1, 2, 3], "cursor-2"),    # First page with next cursor
        ([4, 5, 6], "cursor-3"),    # Second page
        ([7, 8], None),              # Last page
    ]
    page_iter = iter(pages)
    
    async def fetch(cursor):
        return next(page_iter)
    
    items = []
    paginator = CursorPaginator(fetch)
    async for item in paginator:
        items.append(item)
    
    assert items == [1, 2, 3, 4, 5, 6, 7, 8]


@pytest.mark.unit
async def test_async_paginator_empty():
    """Test pagination with empty results."""
    async def fetch(page_size, offset):
        return [], 0
    
    paginator = AsyncPaginator(fetch)
    
    with pytest.raises(StopAsyncIteration):
        await paginator.__anext__()
