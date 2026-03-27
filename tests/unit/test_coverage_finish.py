from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
import asyncio

import httpx
import pytest

from gulp_sdk.client import GulpClient
from gulp_sdk.exceptions import GulpSDKError
from gulp_sdk.websocket import GulpWebSocket, WSMessageType


class _Resp:
    def __init__(self, status_code: int = 200, content: bytes = b"{}", payload: dict | None = None, text: str = ""):
        self.status_code = status_code
        self.content = content
        self._payload = payload if payload is not None else {"status": "success", "data": {}}
        self.text = text or content.decode("utf-8", errors="ignore")

    def json(self):
        return self._payload


@pytest.fixture
def dummy_client():
    client = SimpleNamespace()
    client.ws_id = "ws-test"
    client.token = "tok-test"
    client.base_url = "http://localhost:8080"
    client._request = AsyncMock(return_value={"status": "pending", "req_id": "r1", "data": {}})
    client._raise_for_status = Mock()

    async def _post(*args, **kwargs):
        return _Resp(status_code=200, content=b"{}", payload={"status": "success", "data": {}})

    async def _get(*args, **kwargs):
        return _Resp(status_code=200, content=b"download", payload={"status": "success", "data": {}})

    client._client = SimpleNamespace(
        post=AsyncMock(side_effect=_post),
        get=AsyncMock(side_effect=_get),
    )
    return client


@pytest.mark.unit
async def test_low_modules_req_id_and_optional_branches(dummy_client, tmp_path: Path):
    from gulp_sdk.api.storage import StorageAPI
    from gulp_sdk.api.acl import AclAPI
    from gulp_sdk.api.db import DbAPI
    from gulp_sdk.api.ingest import IngestAPI
    from gulp_sdk.api.enrich import EnrichAPI
    from gulp_sdk.api.auth import AuthAPI
    from gulp_sdk.api.collab import CollabAPI
    from gulp_sdk.api.users import UsersAPI

    storage = StorageAPI(dummy_client)
    acl = AclAPI(dummy_client)
    db = DbAPI(dummy_client)
    ingest = IngestAPI(dummy_client)
    enrich = EnrichAPI(dummy_client)
    auth = AuthAPI(dummy_client)
    collab = CollabAPI(dummy_client)
    users = UsersAPI(dummy_client)

    dummy_client._request.return_value = {"data": {"ok": True}}

    await storage.delete_by_id("op1", "sid1", req_id="r-storage-del")
    await storage.delete_by_tags(operation_id="op1", context_id="ctx1", req_id="r-storage-tags")
    await storage.list_files(operation_id="op1", context_id="ctx1", continuation_token="tok", req_id="r-storage-list")

    dummy_client._client.get = AsyncMock(return_value=_Resp(status_code=500, content=b"err", payload={"status": "error", "data": {"msg": "x"}}))
    await storage.get_file_by_id("op1", "sid1", str(tmp_path / "f.bin"), req_id="r-storage-get")
    assert dummy_client._raise_for_status.call_count >= 1

    await acl.add_granted_user("o1", "note", "u1", req_id="r-acl-au")
    await acl.remove_granted_user("o1", "note", "u1", req_id="r-acl-ru")
    await acl.add_granted_group("o1", "note", "g1", req_id="r-acl-ag")
    await acl.remove_granted_group("o1", "note", "g1", req_id="r-acl-rg")
    await acl.make_private("o1", "note", req_id="r-acl-pr")
    await acl.make_public("o1", "note", req_id="r-acl-pu")

    await db.rebase_by_query("op1", "ws1", 1000, flt={"operation_ids": ["op1"]}, script="ctx._source.x=1", req_id="r-db-reb")
    await db.delete_index("op1", delete_operation=False, req_id="r-db-del")
    await db.list_indexes(req_id="r-db-list")
    await db.refresh_index("op1", req_id="r-db-ref")

    f = tmp_path / "a.evtx"
    f.write_bytes(b"x")
    dummy_client._request.return_value = {"status": "pending", "req_id": "ing1", "data": {}}
    await ingest.file_to_source("src1", str(f), ws_id="ws-x", req_id="r-ing-fs")
    await ingest.file_local(
        "op1", "ctx", "json", "path.log", ws_id="ws-y", plugin_params={"custom_parameters": {}}, flt={"ids": ["1"]}, req_id="r-ing-fl"
    )
    await ingest.file_local_to_source(
        "src1", "path.log", ws_id="ws-z", plugin_params={"custom_parameters": {}}, flt={"ids": ["2"]}, req_id="r-ing-fls"
    )
    await ingest.zip_local("op1", "ctx", "path.zip", ws_id="ws-zz", flt={"ids": ["3"]}, req_id="r-ing-zl")
    await ingest.local_list(req_id="r-ing-ll")

    await enrich.enrich_documents("op1", "enrich_whois", {"f": "v"}, req_id="r-enrich-doc")
    await enrich.enrich_single_id("op1", "d1", "enrich_whois", {"f": "v"}, req_id="r-enrich-one")
    await enrich.update_documents("op1", {"f": "v"}, req_id="r-enrich-upd")
    await enrich.update_single_id("op1", "d1", {"f": "v"}, req_id="r-enrich-upd1")
    await enrich.tag_documents("op1", ["t"], req_id="r-enrich-tag")
    await enrich.tag_single_id("op1", "d1", ["t"], req_id="r-enrich-tag1")
    await enrich.enrich_remove("op1", req_id="r-enrich-rm")

    dummy_client._request.return_value = {"data": [{"name": "gulp", "endpoint": "/login"}]}
    assert isinstance(await auth.get_available_login_api(), list)

    dummy_client._request.return_value = {"data": {"id": "x"}}
    await collab.note_delete("n1", req_id="r-note-del")
    await collab.note_get_by_id("n1", req_id="r-note-get")
    await collab.link_delete("l1", req_id="r-link-del")
    await collab.link_get_by_id("l1", req_id="r-link-get")
    await collab.highlight_delete("h1", req_id="r-h-del")
    await collab.highlight_get_by_id("h1", req_id="r-h-get")
    await collab.glyph_delete("g1", req_id="r-g-del")
    await collab.glyph_get_by_id("g1", req_id="r-g-get")

    dummy_client._request.return_value = {"data": {"id": "u1"}}
    await users.get("u1", req_id="r-user-get")
    await users.delete("u1", req_id="r-user-del")
    await users.session_keepalive(req_id="r-user-keep")


@pytest.mark.unit
async def test_websocket_and_client_remaining_branches(monkeypatch):
    # websocket subscribe auto-connect branch
    connected = '{"type":"ws_connected","req_id":"a","timestamp_msec":1,"payload":{}}'

    class _FakeWS:
        def __init__(self):
            self.sent = []
            self.closed = False
            self._first = True

        async def send(self, msg: str):
            self.sent.append(msg)

        async def recv(self):
            if self._first:
                self._first = False
                return connected
            await asyncio.Event().wait()

        async def close(self):
            self.closed = True

    async def _fake_connect(uri):
        return _FakeWS()

    monkeypatch.setattr("gulp_sdk.websocket.websockets.connect", _fake_connect)
    ws = GulpWebSocket("ws://localhost:8080/ws", "tok", "ws1")
    await ws.subscribe(operation_id="op1", req_id="r1", message_type=WSMessageType.DOCUMENTS_CHUNK)
    assert ws.is_connected
    await ws.disconnect()

    # unsubscribe branch when not connected
    ws2 = GulpWebSocket("ws://localhost:8080/ws", "tok", "ws2")
    await ws2.unsubscribe("r2")

    # __aiter__ branch
    assert ws.__aiter__() is ws

    # connection closed branch in _receive_loop
    from gulp_sdk import websocket as ws_module

    class _ConnClosed(Exception):
        pass

    monkeypatch.setattr(ws_module.websockets.exceptions, "ConnectionClosed", _ConnClosed, raising=False)

    class _ClosedWS:
        async def recv(self):
            raise _ConnClosed("closed")

    ws3 = GulpWebSocket("ws://localhost:8080/ws", "tok", "ws3")
    ws3._connected = True
    ws3._ws = _ClosedWS()
    ws3._reconnect_after_close = AsyncMock(return_value=False)
    await ws3._receive_loop()
    assert ws3.is_connected is False

    # client line 255: force no retry iterations
    c = GulpClient("http://localhost:8080", token="tok")
    c._http_client = SimpleNamespace(
        request=AsyncMock(return_value=_Resp(status_code=500, payload={"status": "error", "data": {"msg": "boom"}}))
    )
    c._retry_policy.max_retries = -1
    with pytest.raises(GulpSDKError):
        await c._request("GET", "/x")

    # client line 277: status error with string payload branch
    with pytest.raises(GulpSDKError):
        c._raise_for_status(500, {"data": "string error"})
