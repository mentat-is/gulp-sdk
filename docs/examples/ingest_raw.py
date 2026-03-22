"""
Ingest raw JSON documents using `ingest.raw`, then query via `query_raw`.
Based on `tests/integration/test_ingest_win_evtx.py` and `tests/integration/test_queries.py`.
"""

import asyncio
from gulp_sdk import GulpClient


async def main():
    async with GulpClient("http://localhost:8080") as client:
        session = await client.auth.login("admin", "admin")
        print(f"Logged in as {session.user_id}")

        op = await client.operations.create("SDK Raw Ingest Example", description="demo")
        print(f"Created operation: {op.id}")

        docs = [
            {
                "@timestamp": "2026-01-01T00:00:00.000Z",
                "event.code": "sdk_raw_1",
                "event.original": "raw ingest event #1",
                "gulp.operation_id": op.id,
                "gulp.context_id": "raw_context",
                "gulp.source_id": "raw_source",
            },
            {
                "@timestamp": "2026-01-01T00:00:01.000Z",
                "event.code": "sdk_raw_2",
                "event.original": "raw ingest event #2",
                "gulp.operation_id": op.id,
                "gulp.context_id": "raw_context",
                "gulp.source_id": "raw_source",
            },
        ]

        ingest_result = await client.ingest.raw(operation_id=op.id, plugin_name="raw", data=docs)
        print(f"Ingest request: {ingest_result.req_id}, status: {ingest_result.status}")

        if ingest_result.req_id:
            stats = await client.ingest.status(op.id, ingest_result.req_id)
            print(f"Status: {stats.get('status')} - {stats}")

        print("Querying ingested docs via query_raw (preview_mode)")
        raw = await client.queries.query_raw(
            operation_id=op.id,
            q=[{"query": {"match_all": {}}}],
            q_options={"preview_mode": True, "limit": 10},
        )

        print("query_raw result:", raw)

        print("Deleting operation")
        await client.operations.delete(op.id)


if __name__ == "__main__":
    asyncio.run(main())
