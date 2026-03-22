"""
Basic usage example — login, create operation, ingest, query.
"""

import asyncio
from gulp_sdk import GulpClient, AuthenticationError


async def main():
    """Run basic workflow example."""
    # Connect to Gulp server
    async with GulpClient("http://localhost:8080") as client:
        # 1. Authenticate
        print("Logging in...")
        try:
            session = await client.auth.login("admin", "admin")
            print(f"✓ Logged in: {session.user_id}")
        except AuthenticationError as e:
            print(f"✗ Login failed: {e.message}")
            return

        # 2. Create operation
        print("\nCreating operation...")
        op = await client.operations.create(
            name="Example Investigation",
            description="Demonstration of SDK usage",
        )
        print(f"✓ Created operation: {op.id} — {op.name}")

        # 3. Get current user info
        print("\nGetting current user...")
        user = await client.users.get_current()
        print(f"✓ Current user: {user.display_name or user.username}")

        # 4. List operations
        print("\nListing operations...")
        count = 0
        async for operation in client.operations.list(limit=10):
            count += 1
            print(f"  - {operation.name} ({operation.id})")
            if count >= 3:
                break

        # 5. Add a note (collaboration)
        print("\nAdding collaboration note...")
        if op.id:
            # Create a dummy document first (in real usage)
            try:
                note = await client.collab.create_note(
                    op.id,
                    "doc-123",
                    "This is an important finding!",
                )
                print(f"✓ Created note: {note.id}")
            except Exception as e:
                print(f"✓ Note creation demo (expected to fail in example): {type(e).__name__}")

        # 6. Logout
        print("\nLogging out...")
        await client.auth.logout()
        print("✓ Logged out")


if __name__ == "__main__":
    asyncio.run(main())
