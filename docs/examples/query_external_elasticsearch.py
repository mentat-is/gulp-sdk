"""
External query example (query_elasticsearch plugin).
This requires a running Gulp with query_elasticsearch plugin configured.
"""

import asyncio
from gulp_sdk import GulpClient


async def main():
    async with GulpClient("http://localhost:8080") as client:
        await client.auth.login("admin", "admin")

        op = await client.operations.create("SDK Query External", description="demo")
        print(f"Created operation: {op.id}")

        # Example custom parameters matching typical local OpenSearch
        plugin_params = {
            "custom_parameters": {
                "uri": "http://localhost:9200",
                "username": "admin",
                "password": "Gulp1234!",
                "index": "gulp-*",
                "context_field": "gulp.context_id",
                "context_type": "context_id",
                "source_field": "gulp.source_id",
                "source_type": "source_id",
            }
        }

        result = await client.queries.query_external(
            operation_id=op.id,
            q={"query": {"match_all": {}}},
            plugin="query_elasticsearch",
            plugin_params=plugin_params,
            q_options={"preview_mode": True, "limit": 5},
        )

        print("query_external result:", result)

        await client.operations.delete(op.id)


if __name__ == "__main__":
    asyncio.run(main())
