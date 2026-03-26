"""
Request status monitoring example: websocket-first vs polling.

This example is linked from `docs/api_reference.md` and demonstrates the preferred
SDK path using `wait_for_request_stats`, with a fallback polling path.
"""

import asyncio
from gulp_sdk import GulpClient
from gulp_sdk.api.request_utils import wait_for_request_stats


async def websocket_request_status_example():
    async with GulpClient("http://localhost:8080") as client:
        await client.auth.login("admin", "admin")

        # Start an async query that returns pending immediately.
        resp = await client.queries.query_raw(
            operation_id="my_op",
            q=[{"query": {"match_all": {}}}],
            req_id="req123",
            wait=False,
        )

        # Wait for terminal status via websocket plus fallback to polling.
        stats = await wait_for_request_stats(client, "req123", timeout=120)
        print("Request status:", stats.get("status"))
        print("Total hits (if available):", stats.get("total_hits"))


async def polling_request_status_example():
    async with GulpClient("http://localhost:8080") as client:
        await client.auth.login("admin", "admin")

        req_id = "req123"

        start = asyncio.get_running_loop().time()
        while True:
            stats = await client.plugins.request_get(req_id)
            status = stats.get("status")
            print("Poll status:", status)
            if status in {"done", "failed", "canceled"}:
                print("Terminal status reached", status)
                break
            if asyncio.get_running_loop().time() - start > 120:
                raise TimeoutError("request status polling timed out")
            await asyncio.sleep(1.0)


async def main():
    print("=== websocket-first status example ===")
    await websocket_request_status_example()

    print("\n=== polling status example ===")
    await polling_request_status_example()


if __name__ == "__main__":
    asyncio.run(main())
