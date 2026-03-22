"""
Collaboration example — create notes and links using Collab API.
"""

import asyncio
from gulp_sdk import GulpClient


async def main():
    async with GulpClient("http://localhost:8080") as client:
        await client.auth.login("admin", "admin")

        op = await client.operations.create("SDK Collab Notes/Links", description="demo")
        print(f"Created operation: {op.id}")

        # Create a note
        note = await client.collab.note_create(
            operation_id=op.id,
            context_id="sdk_context",
            source_id="sdk_source",
            name="Important finding",
            text="Detected suspicious login pattern.",
            tags=["investigation", "suspicious"],
        )
        print(f"Created note: {note.get('id')} (text={note.get('text')})")

        # List notes for operation
        all_notes = await client.collab.note_list(operation_id=op.id)
        print(f"Notes in operation: {len(all_notes)}")

        # Create a link between two documents (illustrative: same doc as self-link)
        link = await client.collab.link_create(
            operation_id=op.id,
            doc_id_from="doc-001",
            doc_ids=["doc-001"],
            name="self-link",
            description="Sample link from a doc to itself.",
            tags=["demo"],
        )
        print(f"Created link: {link.get('id')}")

        # Clean up
        if note.get("id"):
            await client.collab.note_delete(note.get("id"))
            print("Deleted note")
        if link.get("id"):
            await client.collab.link_delete(link.get("id"))
            print("Deleted link")

        await client.operations.delete(op.id)
        print("Deleted operation")


if __name__ == "__main__":
    asyncio.run(main())
