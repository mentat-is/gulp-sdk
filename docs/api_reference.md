# SDK API Reference (Quick Guide)

This page maps the main `gulp-sdk` API groups to the corresponding methods. All methods are available on `GulpClient` as properties.

## Client entry point

- `GulpClient(base_url, token=None, timeout=30.0, ws_auto_connect=True)`
- Context manager:
  - `async with GulpClient(...) as client:`
- WebSocket:
  - `async with client.websocket() as ws:`
  - `await client.ensure_websocket()`
  - `await ws.acknowledge_documents_chunk(req_id, chunk_number)` after
    durably processing an `ack_required` chunk from a query using
    `q_options={"ws_ack_window": ...}`
  - `ws.server_capabilities` includes `docs_chunk_ack_v1` when supported
- SDK build version:
  - `client.sdk_version()`
- Server version API:
  - `await client.version()` (authenticated)

## Authentication (`client.auth`)

- `login(username, password)`
- `logout()`
- `refresh()`

## Operations (`client.operations`)

- `create(name, description)`
- `get(operation_id)`
- `list()`
- `delete(operation_id)`
- `context_create`, `source_create`, etc.

## Documents (`client.documents`)

- `get(operation_id, document_id)`
- `list(operation_id)`
- `create`/`update`/`delete` document operations

## Ingest (`client.ingest`)

- `file(operation_id, plugin_name, file_path, context_name, ws_id, params)`
- `file_to_source(source_id, file_path, plugin, plugin_params, flt, ws_id, req_id)` (`plugin_params` is required when overriding `plugin`; `{}` is allowed)
- `raw(operation_id, plugin_name, data, params)`
- `status(operation_id, req_id)`
- `preview(operation_id, plugin_name, file_path, params)`

## Queries (`client.queries`)

- `query_raw(operation_id, q, ws_id, q_options, req_id)`
- `query_raw_paginate(operation_id, q, q_options, pagination_mode=None, pit_id=None, search_after=None, req_id=None)`
- `query_raw_paginate_close(operation_id, pit_id, req_id=None)`
- `query_single_id(operation_id, doc_id, req_id)`
- `query_gulp(operation_id, ws_id, flt, q_options, req_id)`
- `query_external(operation_id, q, plugin, plugin_params, ws_id, q_options, req_id)`
- `query_sigma(...)`
- `query_history_get` (returns entries newest first), `query_operations`, etc.

### Raw pagination

Offset pagination remains the default and existing calls continue to work:

```python
page = await client.queries.query_raw_paginate(
    "my-operation",
    {"query": {"match_all": {}}},
    {"limit": 50, "offset": 100},
)
```

Use PIT mode when results must remain stable across deep or direct page jumps.
The first request omits `pit_id`; subsequent requests reuse the returned
`pit_id` and may pass the returned `search_after` cursor. Cursor elements are
OpenSearch sort values and may be strings, numbers, booleans, or null values.

```python
page = await client.queries.query_raw_paginate(
    "my-operation",
    {"query": {"match_all": {}}},
    {"limit": 50, "offset": 0, "sort": {"@timestamp": "asc"}},
    pagination_mode="pit",
)

next_page = await client.queries.query_raw_paginate(
    "my-operation",
    {"query": {"match_all": {}}},
    {"limit": 50, "offset": 50, "sort": {"@timestamp": "asc"}},
    pagination_mode="pit",
    pit_id=page["pit_id"],
    search_after=page.get("search_after"),
)

await client.queries.query_raw_paginate_close(
    "my-operation", next_page["pit_id"]
)
```

Always close a PIT when pagination finishes. If a PIT expires, start again
without `pit_id` to open a new snapshot.

## Collaboration (`client.collab`)

- `note_create`, `note_update`, `note_delete`, `note_list`
- `note_add_attachment(note_id, file_path, title=None, mime_type=None)`
- `note_delete_attachment(note_id, attachment_id)`
- `note_list_attachments(note_id)`
- `note_get_attachment(note_id, attachment_id, output_path)`
- `link_create`, `link_update`, `link_delete`, `link_list`
- `highlight_create`, `highlight_update`, `highlight_delete` (if supported)

## Plugins (`client.plugins`)

- `version(req_id=None)` - server `/version` endpoint
- `request_get`, `request_delete`, `request_list` (equivalent to plugin request tracking)
- plugin-specific utilities through server plugin endpoints

## Storage (`client.storage`)

- `list_files(operation_id, context_id, continuation_token, max_results, req_id)`
- `delete_by_id(operation_id, storage_id, req_id)`
- `delete_by_tags(operation_id, context_id, req_id)`
- `get_file_by_id(operation_id, storage_id, output_path, req_id)`

## ACL (`client.acl`)

- Usually manages object permissions; check method names in `src/gulp_sdk/api/acl.py`.

## DB / OpenSearch (`client.db`)

- Index mappings, resets, management endpoints (see `src/gulp_sdk/api/db.py`).

## Request status updates: websocket vs polling

Async operations (ingest/query) may return `pending` and stream results through websocket notifications.

- Preferred: `wait_for_request_stats(client, req_id, timeout, ws_callback=None)` in `gulp_sdk.api.request_utils`.
- Alternative: poll with `client.plugins.request_get(req_id)`.

For full examples, see:

- `docs/examples/request_status_vs_polling.py`
- Advanced integration example: `tests/integration/test_stress.py` in the main `gulp` repository.

---

For deeper info and method argument details, consult the source and docstrings in `src/gulp_sdk/api/`.
