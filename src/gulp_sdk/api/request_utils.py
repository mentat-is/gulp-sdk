import asyncio
from typing import Any

from gulp_sdk.exceptions import NotFoundError


async def wait_for_request_stats(
    client: Any,
    req_id: str,
    timeout: int,
) -> dict[str, Any]:
    """Wait for request stats terminal status, tolerating transient 404 stats."""
    loop = asyncio.get_running_loop()
    deadline = None if timeout == 0 else loop.time() + timeout
    last_stats: dict[str, Any] = {"status": "ongoing", "req_id": req_id}

    while True:
        try:
            stats = await client.plugins.request_get(req_id)
            if isinstance(stats, dict):
                last_stats = stats
            status = str((stats or {}).get("status", "")).lower()
            if status in {"done", "failed", "canceled"}:
                return stats
        except NotFoundError as exc:
            msg = str(exc).lower()
            transient_stats_404 = "gulprequeststats" in msg and "not found" in msg
            if not transient_stats_404:
                raise

        if deadline is not None and loop.time() >= deadline:
            return last_stats
        await asyncio.sleep(1)
