# Gulp SDK Quick Start

This guide is a concise reference for installing and using the Python SDK against a local `gulp` server.

## 1. Prerequisites

- Python 3.12 or 3.13 (matching backend recommendation).
- `gulp` running locally on `http://localhost:8080`.
- Optional: `docker compose --profile dev up -d` from the parent `gulp` repo.

## 2. Install SDK

```bash
pip install gulp-sdk
```

or for local development (current repository name is `gulp-sdk`):

```bash
git clone https://github.com/mentat-is/gulp-sdk.git
cd gulp-sdk
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

## 3. Basic usage

```python
import asyncio
from gulp_sdk import GulpClient

async def main():
    async with GulpClient("http://localhost:8080", ws_auto_connect=True) as client:
        session = await client.auth.login("admin", "admin")
        print(f"Logged in as {session.user_id}")

        op = await client.operations.create(name="SDK Quickstart", description="Test")
        print(f"Operation {op.id}")

        async for doc in client.documents.list(operation_id=op.id):
            print(doc.id, doc.raw.get("@timestamp"))

asyncio.run(main())
```

## 4. WebSocket status vs polling

This doc already includes the full details and examples in `docs/api_reference.md`.

Advanced scenarios including `query_sigma_zip` and note creation are in `tests/integration/test_stress.py`.

## 5. Common environment variables

These are used by test fixtures and example scripts; the SDK core (`src/gulp_sdk`) does not directly read them.

- `GULP_BASE_URL`: Gulp server URL for SDK use (default `http://localhost:8080`).
- `GULP_TEST_USER`: Test user for integration flows (default `admin`).
- `GULP_TEST_PASSWORD`: Test password for integration flows (default `admin`).
- `GULP_TEST_TOKEN`: Optional test bearer token.

## 5. Testing

Run unit tests in SDK repo:

```bash
pytest -v -s -x tests/unit
```

Run integration tests (requires local gULP server):

```bash
pytest -v -s -x tests/integration
```

## 6. References

- `gulp` server docs: `../gulp/docs` (architecture, plugins, ingestion).
- Example scripts: `docs/examples/basic_usage.py`, `docs/examples/websocket_monitoring.py`.
