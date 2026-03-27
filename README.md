# Gulp Python SDK

Async Python SDK for the [Gulp](https://github.com/mentat-is/gulp) document analysis and collaboration platform.

## Features

- **Fully Async** — Built on `httpx` and `asyncio` for high-performance, non-blocking I/O
- **Complete API Coverage** — All major REST endpoints (operations, documents, ingestion, queries, users, collaboration)
- **WebSocket Support** — Real-time ingestion progress, query results, and collaborative updates
- **Type-Safe** — Full type hints, Pydantic models, and static typing support
- **Error Handling** — Comprehensive exception hierarchy with HTTP status codes and response data
- **Pagination** — Async iterators for large result sets
- **Retry Logic** — Automatic exponential backoff on transient failures

## Installation
```bash
pip install gulp-sdk
```

## Quick Start

If you prefer a dedicated guide, see [docs/quickstart.md](docs/quickstart.md).

```python
import asyncio
from gulp_sdk import GulpClient

async def main():
    # Connect to Gulp server
    async with GulpClient("http://localhost:8080") as client:
        # Login
        session = await client.auth.login("user@example.com", "password")
        print(f"Logged in: {session.user_id}")

        # Create operation
        op = await client.operations.create(
            name="My Investigation",
            description="Analyze event logs"
        )
        print(f"Created operation: {op.id}")

        # Get current user
        user = await client.users.get_current()
        print(f"Current user: {user.display_name}")

asyncio.run(main())
```

## API Reference

- [SDK API reference](docs/api_reference.md)

## Documentation site

This repository includes official docs for local or remote hosting:

- Local preview: `mkdocs serve`
- Build HTML: `mkdocs build`

### Run docs locally

```bash
pip install -r requirements-docs.txt
mkdocs serve
```

### Documentation pages

- Quick start: `docs/quickstart.md`
- API reference: `docs/api_reference.md`
- Examples: `docs/examples/` (scripts)

### Authentication

```python
# Login with credentials
session = await client.auth.login("user", "password")

# Token is automatically stored
# Logout
await client.auth.logout()
```

### Operations

```python
# Create operation
op = await client.operations.create("Name", "Description")

# Get operation
op = await client.operations.get(op.id)
```

### Documents

```python
# Get document
doc = await client.documents.get(operation_id, document_id)

# Query documents (with async iteration)
async for doc in client.documents.list(operation_id):
    print(doc.content[:100])
```

### Ingestion

```python
# Ingest file
job = await client.ingest.file(operation_id, plugin="json", file_path="/path/to/file.json")

# Ingest raw data
job = await client.ingest.raw(operation_id, plugin="json", data={"key": "value"})

# Monitor with WebSocket
async for progress in client.ingest.stream(operation_id, req_id=job.req_id):
    print(f"Progress: {progress.percent}%")
```

### Collaboration

```python
# Add note
note = await client.collab.create_note(operation_id, document_id, "Important finding")

# Create link between documents
link = await client.collab.create_link(doc_id_from, doc_id_to, "related_to")
```

## WebSocket Real-Time Updates

### Auto-Managed Mode

```python
async with GulpClient("http://localhost:8080", ws_auto_connect=True) as client:
    # WebSocket automatically connected
    
    # Subscribe to document updates
    await client.websocket.subscribe(operation_id)
    
    # Receive messages
    async for message in client.websocket:
        print(f"Update: {message.type} — {message.data}")
```

### Manual Mode

```python
async with GulpClient("http://localhost:8080") as client:
    async with client.websocket() as ws:
        # Authenticate and subscribe
        await ws.subscribe(operation_id, req_id="ingest-123")
        
        # Receive real-time updates
        async for message in ws:
            if message.type == "WSDATA_INGEST_RAW_PROGRESS":
                print(f"Ingestion: {message.data.percent}%")
            elif message.type == "WSDATA_QUERY_DONE":
                print(f"Query complete: {len(message.data.documents)} results")
```

### Request status: websocket vs polling

For async operations, realtime websocket monitoring is recommended; polling is a fallback.

- WebSocket pattern: use `wait_for_request_stats(client, req_id, timeout, ws_callback=...)`.
- Polling: `client.plugins.request_get(req_id)` in a loop.

See `docs/api_reference.md` for details and examples.

For advanced websocket note/QUERY_DONE tracking, consult `tests/integration/test_stress.py`.

## Error Handling

```python
from gulp_sdk import (
    GulpClient,
    AuthenticationError,
    PermissionError,
    NotFoundError,
    ValidationError,
    GulpSDKError,
)

async with GulpClient("http://localhost:8080") as client:
    try:
        await client.auth.login("user", "pass")
    except AuthenticationError as e:
        print(f"Login failed: {e.message}")
    except GulpSDKError as e:
        print(f"SDK error: {e.message} (status: {e.status_code})")
```

## Configuration

Environment variables are used by tests and example scripts (fixtures) to parameterize connection settings. The SDK core methods in `src/gulp_sdk` accept explicit arguments and do not read env vars directly.

```bash
GULP_BASE_URL=http://localhost:8080        # Server URL (default: localhost:8080)
GULP_TEST_USER=admin                       # Default test user for integration tests
GULP_TEST_PASSWORD=admin                   # Default test password for integration tests
GULP_TEST_TOKEN=                           # Optional token for test auth
GULP_REQUEST_TIMEOUT=30                    # HTTP timeout in seconds (default: 30)
GULP_WS_TIMEOUT=300                        # WebSocket timeout (default: 300)
GULP_LOG_LEVEL=INFO                        # Logging level (default: INFO)
```

Or programmatically:

```python
client = GulpClient(
    base_url="http://localhost:8080",
    timeout=30.0,
    ws_auto_connect=True,
)
```

## Examples

See `docs/examples/` for complete working examples:

- [basic_usage.py](docs/examples/basic_usage.py) — Login, create operation, ingest, query
- [websocket_monitoring.py](docs/examples/websocket_monitoring.py) — Real-time ingestion progress
- [ingest_raw.py](docs/examples/ingest_raw.py) — Raw JSON ingestion + query_raw preview
- [query_gulp_preview.py](docs/examples/query_gulp_preview.py) — query_gulp preview with simple filter
- [collab_notes_links.py](docs/examples/collab_notes_links.py) — Collaboration notes and links workflow
- [storage_list_files.py](docs/examples/storage_list_files.py) — List and delete storage files workflow
- [query_external_elasticsearch.py](docs/examples/query_external_elasticsearch.py) — External query with query_elasticsearch plugin
- [context_source_management.py](docs/examples/context_source_management.py) — Create and manage contexts and sources, complete incident setup

For additional workflows, consult the integration tests in `tests/integration/` and the main `gulp` docs for plugin-specific ingestion and query patterns.

## Testing

Run tests:

```bash
# Unit tests (no dependencies)
pytest -v -s -x tests/unit

# minimal integration tests, requires live Gulp server on localhost:8080
pytest -v -s -x tests/integration  
```

> to run full integration test suite, look at gulp [gulp testing documentation](https://github.com/mentat-is/gulp/blob/develop/docs/testing.md)


