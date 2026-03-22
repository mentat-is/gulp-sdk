"""
WebSocket example — Real-time ingestion progress monitoring.
"""

import asyncio
from gulp_sdk import GulpClient, WSMessageType


async def monitor_ingestion():
    """Monitor ingestion progress via WebSocket."""
    async with GulpClient("http://localhost:8080") as client:
        # Login first
        session = await client.auth.login("admin", "admin")
        print(f"Logged in: {session.user_id}\n")

        # Create operation
        op = await client.operations.create("Ingestion Monitor Demo")
        print(f"Created operation: {op.id}\n")

        # Start ingestion (simulated)
        print("Starting ingestion...")
        # ingest_result = await client.ingest.file(op.id, "json", "data.json")
        # req_id = ingest_result.req_id
        req_id = "ingestion-123"  # Example req_id

        # Method 1: Manual WebSocket with explicit subscription
        print("\n=== Manual WebSocket Mode ===")
        async with client.websocket() as ws:
            # Subscribe to ingestion progress
            await ws.subscribe(operation_id=op.id, req_id=req_id)

            # Listen for messages
            print("Listening for updates...")
            try:
                async for message in ws:
                    if message.type == WSMessageType.INGEST_RAW_PROGRESS:
                        progress = message.data.get("percent", 0)
                        count = message.data.get("count", 0)
                        print(f"Progress: {progress}% (documents: {count})")

                        if progress >= 100:
                            break
            except asyncio.TimeoutError:
                print("Timeout waiting for messages")

        # Method 2: Auto-managed mode with callbacks (future enhancement)
        print("\n=== Callback-Based Mode ===")

        async def on_ingest_progress(message):
            """Callback for progress updates."""
            progress = message.data.get("percent", 0)
            count = message.data.get("count", 0)
            print(f"[Callback] Progress: {progress}% (documents: {count})")

        # This would be auto-managed in future versions
        # client.on_message(WSMessageType.INGEST_RAW_PROGRESS, on_ingest_progress)


if __name__ == "__main__":
    asyncio.run(monitor_ingestion())
