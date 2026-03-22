"""
Example: create operation, ingest one raw doc, and run `query_gulp` in preview mode.
Inspired by `tests/integration/test_queries.py`.
"""

import asyncio
from gulp_sdk import GulpClient


async def main():
    async with GulpClient("http://localhost:8080") as client:
        await client.auth.login("admin", "admin")

        op = await client.operations.create("SDK Query Gulp Preview", description="demo")
        print(f"Operation created: {op.id}")

        # ingest one document
        await client.ingest.raw(
            operation_id=op.id,
            plugin_name="raw",
            data={
                "@timestamp": "2026-01-01T01:00:00.000Z",
                "event.original": "query_gulp preview doc",
                "gulp.operation_id": op.id,
                "gulp.context_id": "query_gulp_context",
                "gulp.source_id": "query_gulp_source",
            },
        )

        # query using simplified Gulp filter (preview)
        result = await client.queries.query_gulp(
            operation_id=op.id,
            flt={"operation_ids": [op.id]},
            q_options={"preview_mode": True, "limit": 10},
        )

        print("query_gulp preview result:", result)

        await client.operations.delete(op.id)


if __name__ == "__main__":
    asyncio.run(main())
