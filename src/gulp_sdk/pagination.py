"""
Async pagination helpers for handling large result sets.

Supports both cursor-based and offset-based pagination.
"""

from typing import AsyncIterator, Callable, TypeVar, Generic, Any
from dataclasses import dataclass

T = TypeVar("T")


@dataclass(frozen=True)
class PaginationParams:
    """Pagination parameters."""

    page_size: int = 50
    cursor: str | None = None
    offset: int = 0


class AsyncPaginator(Generic[T]):
    """
    Async iterator for paginated API results.

    Automatically fetches next pages as iteration continues.

    Example:
        ```python
        async def fetch_page(page_size: int, offset: int):
            response = await client._request("GET", "/documents", params={
                "limit": page_size,
                "offset": offset,
            })
            return response.get("data", {}).get("items", []), response.get("data", {}).get("total", 0)

        paginator = AsyncPaginator(fetch_page, page_size=50)
        async for item in paginator:
            print(item)
        ```
    """

    def __init__(
        self,
        fetch_func: Callable[[int, int], Any],
        page_size: int = 50,
        total_items: int | None = None,
    ) -> None:
        """
        Initialize async paginator.

        Args:
            fetch_func: Coroutine function(page_size, offset) -> (items, total)
            page_size: Items per page
            total_items: Optional total item count to stop pagination
        """
        self.fetch_func = fetch_func
        self.page_size = page_size
        self.total_items = total_items

        # State
        self._offset = 0
        self._fetched_count = 0
        self._current_batch: list[T] = []
        self._batch_index = 0
        self._exhausted = False

    async def __anext__(self) -> T:
        """Get next item."""
        # Fetch next batch if needed
        while self._batch_index >= len(self._current_batch):
            if self._exhausted:
                raise StopAsyncIteration

            self._current_batch, total = await self.fetch_func(
                self.page_size, self._offset
            )

            if not self._current_batch:
                self._exhausted = True
                raise StopAsyncIteration

            self._offset += self.page_size
            self._batch_index = 0

            # Check if reached total
            if self.total_items and self._fetched_count >= self.total_items:
                self._exhausted = True

        item = self._current_batch[self._batch_index]
        self._batch_index += 1
        self._fetched_count += 1
        return item

    def __aiter__(self):
        """Async iterator protocol."""
        return self


class CursorPaginator(Generic[T]):
    """
    Async iterator for cursor-based pagination.

    Some APIs use opaque cursors instead of offsets.

    Example:
        ```python
        async def fetch_page(cursor: str | None):
            response = await client._request("GET", "/documents", params={
                "cursor": cursor,
                "limit": 50,
            })
            data = response.get("data", {})
            return data.get("items", []), data.get("next_cursor")

        paginator = CursorPaginator(fetch_page)
        async for item in paginator:
            print(item)
        ```
    """

    def __init__(self, fetch_func: Callable[[str | None], Any]) -> None:
        """
        Initialize cursor paginator.

        Args:
            fetch_func: Coroutine function(cursor) -> (items, next_cursor)
        """
        self.fetch_func = fetch_func

        # State
        self._cursor: str | None = None
        self._current_batch: list[T] = []
        self._batch_index = 0
        self._exhausted = False

    async def __anext__(self) -> T:
        """Get next item."""
        # Fetch next batch if needed
        while self._batch_index >= len(self._current_batch):
            if self._exhausted:
                raise StopAsyncIteration

            self._current_batch, self._cursor = await self.fetch_func(self._cursor)

            if not self._current_batch or not self._cursor:
                self._exhausted = True

            self._batch_index = 0

            if not self._current_batch:
                raise StopAsyncIteration

        item = self._current_batch[self._batch_index]
        self._batch_index += 1
        return item

    def __aiter__(self):
        """Async iterator protocol."""
        return self
