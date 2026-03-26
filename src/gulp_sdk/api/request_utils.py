import asyncio
from typing import Any, Callable

from gulp_sdk.exceptions import NotFoundError
from gulp_sdk.websocket import WSMessage, WSMessageType


_TERMINAL_STATUSES: frozenset[str] = frozenset({"done", "failed", "canceled"})

# Message types that carry the global GulpRequestStats object in payload.obj
# and therefore represent a request-level terminal signal when status is terminal.
# QUERY_DONE and INGEST_SOURCE_DONE are intentionally omitted: they are per-query
# / per-source events, NOT per-request signals, and resolving on them would return
# incomplete aggregated data (no completed_queries, no records_ingested, etc.).
_WS_TERMINAL_TYPES: tuple[WSMessageType, ...] = (
    WSMessageType.STATS_CREATE,
    WSMessageType.STATS_UPDATE,
    WSMessageType.INGEST_RAW_PROGRESS,
    WSMessageType.REBASE_DONE,
    WSMessageType.ERROR,
)

# Fast lookup set for terminal-type filtering inside the hot callback path.
_TERMINAL_TYPE_VALUES: frozenset[str] = frozenset(t.value for t in _WS_TERMINAL_TYPES)

# Progress/intermediate event types that are forwarded to an optional user
# ws_callback but do NOT resolve the wait future.
_WS_PROGRESS_TYPES: tuple[WSMessageType, ...] = (
    WSMessageType.QUERY_DONE,
    WSMessageType.INGEST_SOURCE_DONE,
    WSMessageType.DOCUMENTS_CHUNK,
    WSMessageType.QUERY_GROUP_MATCH,
)

def _build_ws_result(req_id: str, status: str, message: WSMessage) -> dict[str, Any]:
    payload: dict[str, Any]
    if isinstance(message.data, dict):
        obj = message.data.get("obj")
        if isinstance(obj, dict):
            payload = dict(obj)
        else:
            payload = dict(message.data)
    else:
        payload = {}
    payload.setdefault("req_id", req_id)
    payload["status"] = status
    if message.type == WSMessageType.ERROR.value and not payload.get("errors"):
        payload["errors"] = [str(message.data)]
    return payload


def _extract_ws_status(message: WSMessage) -> str | None:
    if message.type == WSMessageType.ERROR.value:
        return "failed"
    if not isinstance(message.data, dict):
        return None

    # Server websocket packets commonly expose the collab object under payload.obj.
    # Stats notifications therefore carry status in payload.obj.status.
    candidates: list[dict[str, Any]] = [message.data]
    obj = message.data.get("obj")
    if isinstance(obj, dict):
        candidates.append(obj)

    for candidate in candidates:
        status = candidate.get("status")
        if not isinstance(status, str):
            continue
        normalized = status.lower()
        if normalized in _TERMINAL_STATUSES:
            return normalized
    return None


def _safe_future_result(future: asyncio.Future[dict[str, Any]]) -> dict[str, Any] | None:
    if future.cancelled():
        return None
    exc = future.exception()
    if exc is not None:
        return None
    result = future.result()
    if isinstance(result, dict):
        return result
    return None


async def _subscribe_ws_waiter(
    client: Any,
    req_id: str,
    ws_callback: Callable[[WSMessage], None] | None = None,
) -> tuple[asyncio.Future[dict[str, Any]], Any, Any] | None:
    if not hasattr(client, "ensure_websocket"):
        return None

    try:
        ws = await client.ensure_websocket()
    except Exception:
        return None

    loop = asyncio.get_running_loop()
    future: asyncio.Future[dict[str, Any]] = loop.create_future()
    subscriptions: list[tuple[WSMessageType, Any]] = []

    def _on_message(message: WSMessage) -> None:
        if message.req_id != req_id:
            return
        # Forward every matching message to the optional user callback first.
        if ws_callback is not None:
            try:
                ws_callback(message)
            except Exception:
                pass
        # Only resolve the future for terminal-type messages (GulpRequestStats).
        if future.done():
            return
        if message.type not in _TERMINAL_TYPE_VALUES:
            return
        status = _extract_ws_status(message)
        if status is None:
            return
        future.set_result(_build_ws_result(req_id, status, message))

    # Always subscribe to terminal types; add progress types when a callback is provided.
    subscribe_types = list(_WS_TERMINAL_TYPES) + (
        list(_WS_PROGRESS_TYPES) if ws_callback is not None else []
    )
    for message_type in subscribe_types:
        try:
            ws.on_message(message_type, _on_message)
            subscriptions.append((message_type, _on_message))
        except Exception:
            continue

    async def _cleanup() -> None:
        off_message = getattr(ws, "off_message", None)
        if callable(off_message):
            for message_type, callback in subscriptions:
                try:
                    off_message(message_type, callback)
                except Exception:
                    pass
        if not future.done():
            future.cancel()

    return future, _cleanup, ws


async def wait_for_request_stats(
    client: Any,
    req_id: str,
    timeout: int,
    ws_callback: Callable[[WSMessage], None] | None = None,
) -> dict[str, Any]:
    """Wait for request stats terminal status, tolerating transient 404 stats."""
    loop = asyncio.get_running_loop()
    deadline = None if timeout == 0 else loop.time() + timeout
    last_stats: dict[str, Any] = {"status": "ongoing", "req_id": req_id}
    ws_subscription = await _subscribe_ws_waiter(client, req_id, ws_callback=ws_callback)
    ws_future: asyncio.Future[dict[str, Any]] | None = None
    ws_cleanup = None
    ws_client = None
    use_polling = True
    if ws_subscription is not None:
        ws_future, ws_cleanup, ws_client = ws_subscription
        use_polling = False

    try:
        while True:
            if ws_future is not None and ws_future.done():
                ws_result = _safe_future_result(ws_future)
                if ws_result is not None:
                    return ws_result
                ws_future = None
                use_polling = True

            if not use_polling and ws_client is not None:
                is_connected = getattr(ws_client, "is_connected", True)
                if not is_connected:
                    recovered = await _subscribe_ws_waiter(
                        client,
                        req_id,
                        ws_callback=ws_callback,
                    )
                    if recovered is not None:
                        if ws_cleanup is not None:
                            await ws_cleanup()
                        ws_future, ws_cleanup, ws_client = recovered
                        use_polling = False
                        continue
                    use_polling = True

            if use_polling:
                try:
                    stats = await client.plugins.request_get(req_id)
                    if isinstance(stats, dict):
                        last_stats = stats
                    status = str((stats or {}).get("status", "")).lower()
                    if status in _TERMINAL_STATUSES:
                        return stats
                except NotFoundError as exc:
                    msg = str(exc).lower()
                    transient_stats_404 = "gulprequeststats" in msg and "not found" in msg
                    if not transient_stats_404:
                        raise

            if deadline is not None and loop.time() >= deadline:
                if ws_future is not None and ws_future.done():
                    ws_result = _safe_future_result(ws_future)
                    if ws_result is not None:
                        return ws_result
                if not use_polling:
                    try:
                        stats = await client.plugins.request_get(req_id)
                        if isinstance(stats, dict):
                            last_stats = stats
                    except NotFoundError:
                        pass
                return last_stats

            sleep_for = 1.0
            if deadline is not None:
                sleep_for = min(sleep_for, max(0.0, deadline - loop.time()))
            if sleep_for <= 0:
                return last_stats

            if ws_future is None or use_polling:
                await asyncio.sleep(sleep_for)
                continue

            done, _ = await asyncio.wait({ws_future}, timeout=sleep_for)
            if done:
                ws_result = _safe_future_result(ws_future)
                if ws_result is not None:
                    return ws_result
    finally:
        if ws_cleanup is not None:
            await ws_cleanup()
