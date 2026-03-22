# SDK API Reference (Quick Guide)

This page maps the main `gulp-sdk` API groups to the corresponding methods. All methods are available on `GulpClient` as properties.

## Client entry point

- `GulpClient(base_url, token=None, timeout=30.0, ws_auto_connect=True)`
- Context manager:
  - `async with GulpClient(...) as client:`
- WebSocket:
  - `async with client.websocket() as ws:`
  - `await client.ensure_websocket()`

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
- `raw(operation_id, plugin_name, data, params)`
- `zip(operation_id, plugin_name, zipfile_path, params)`
- `status(operation_id, req_id)`
- `preview(operation_id, plugin_name, file_path, params)`

## Queries (`client.queries`)

- `query_raw(operation_id, q, ws_id, q_options, req_id)`
- `query_gulp(operation_id, ws_id, flt, q_options, req_id)`
- `query_external(operation_id, q, plugin, plugin_params, ws_id, q_options, req_id)`
- `query_sigma(...)`
- `query_history_get`, `query_operations`, etc.

## Collaboration (`client.collab`)

- `note_create`, `note_update`, `note_delete`, `note_list`
- `link_create`, `link_update`, `link_delete`, `link_list`
- `highlight_create`, `highlight_update`, `highlight_delete` (if supported)

## Plugins (`client.plugins`)

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

---

For deeper info and method argument details, consult the source and docstrings in `src/gulp_sdk/api/`.
