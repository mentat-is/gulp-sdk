"""
Storage example — list files and (optionally) delete by storage_id.
"""

import asyncio
from gulp_sdk import GulpClient


async def main():
    async with GulpClient("http://localhost:8080") as client:
        await client.auth.login("admin", "admin")

        op = await client.operations.create("SDK Storage Example", description="demo")
        print(f"Created operation: {op.id}")

        # List files for this operation
        files = await client.storage.list_files(operation_id=op.id)
        print(f"Files count: {len(files.get('files', []))}")

        # Delete a file by storage_id (if present)
        if files.get("files"):
            first_file = files["files"][0]
            storage_id = first_file.get("storage_id")
            if storage_id:
                print(f"Deleting file {storage_id}")
                await client.storage.delete_by_id(operation_id=op.id, storage_id=storage_id)

        await client.operations.delete(op.id)
        print("Deleted operation")


if __name__ == "__main__":
    asyncio.run(main())
