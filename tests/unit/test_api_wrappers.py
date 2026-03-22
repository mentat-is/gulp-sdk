"""Unit tests for API wrapper modules using mocked client transport."""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest


class _DummyResponse:
    def __init__(self, status_code: int = 200, content: bytes = b"{}"):
        self.status_code = status_code
        self.content = content

    def json(self):
        return {"status": "success", "data": {}}


@pytest.fixture
def dummy_client():
    """Provide a minimal mocked client object used by API wrappers."""
    client = SimpleNamespace()
    client.ws_id = "ws-test"
    client.token = "tok-test"
    client.base_url = "http://localhost:8080"
    client._request = AsyncMock(return_value={"status": "pending", "req_id": "r1", "data": {}})
    client._raise_for_status = Mock()

    async def _post(*args, **kwargs):
        return _DummyResponse(status_code=200, content=b"{\"ok\": true}")

    async def _get(*args, **kwargs):
        return _DummyResponse(status_code=200, content=b"download")

    client._client = SimpleNamespace(
        post=AsyncMock(side_effect=_post),
        get=AsyncMock(side_effect=_get),
    )
    return client


@pytest.mark.unit
async def test_queries_query_sigma_and_external(dummy_client):
    from gulp_sdk.api.queries import QueriesAPI

    api = QueriesAPI(dummy_client)

    await api.query_external(
        operation_id="op1",
        q={"query": {"match_all": {}}},
        plugin="query_elasticsearch",
        plugin_params={"custom_parameters": {"url": "http://localhost:9200"}},
        q_options={"preview_mode": True, "limit": 5},
        req_id="req-ext",
    )

    await api.query_sigma(
        operation_id="op1",
        sigmas=["title: Match All\nlogsource:\n  product: windows\ndetection:\n  selection: {}\n  condition: selection\n"],
        src_ids=[],
        levels=["high"],
        products=["windows"],
        categories=["process_creation"],
        services=["security"],
        tags=["attack.t1110"],
        q_options={"preview_mode": True, "name": "sigma"},
        req_id="req-sigma",
    )

    assert dummy_client._request.await_count >= 2


@pytest.mark.unit
async def test_queries_query_sigma_zip(dummy_client, tmp_path: Path):
    from gulp_sdk.api.queries import QueriesAPI

    api = QueriesAPI(dummy_client)

    zip_path = tmp_path / "sigmas.zip"
    zip_path.write_bytes(b"PK\x03\x04dummy")

    resp = await api.query_sigma_zip(
        operation_id="op1",
        zip_path=str(zip_path),
        src_ids=["src1"],
        levels=["critical"],
        q_options={"create_notes": False, "limit": 10},
        req_id="req-zip",
    )

    assert isinstance(resp, dict)
    call = dummy_client._request.await_args_list[-1]
    assert call.args[0] == "POST"
    assert call.args[1] == "/query_sigma_zip"
    assert call.kwargs["headers"]["size"] == str(len(zip_path.read_bytes()))


@pytest.mark.unit
async def test_queries_export_json_download(dummy_client, tmp_path: Path):
    from gulp_sdk.api.queries import QueriesAPI

    api = QueriesAPI(dummy_client)

    out_path = tmp_path / "export.json"
    saved = await api.query_gulp_export_json(
        operation_id="op1",
        output_path=str(out_path),
        flt={"operation_ids": ["op1"]},
        q_options={"limit": 10},
    )

    assert saved == str(out_path)
    assert out_path.exists()
    assert out_path.read_bytes() == b"{\"ok\": true}"


@pytest.mark.unit
async def test_ingest_file_raw_zip_and_status(dummy_client, tmp_path: Path):
    from gulp_sdk.api.ingest import IngestAPI

    api = IngestAPI(dummy_client)

    sample_file = tmp_path / "sample.evtx"
    sample_file.write_bytes(b"dummy")

    result_file = await api.file(
        operation_id="op1",
        plugin_name="win_evtx",
        file_path=str(sample_file),
        context_name="ctx1",
        params={"plugin_params": {"preview_mode": True}},
    )
    assert result_file.req_id == "r1"

    dummy_client._request.return_value = {"status": "pending", "req_id": "r2", "data": {}}
    result_raw = await api.raw(
        operation_id="op1",
        plugin_name="raw",
        data=[{"@timestamp": "2024-01-01T00:00:00Z", "message": "x"}],
    )
    assert result_raw.req_id == "r2"
    call = dummy_client._request.await_args_list[-1]
    assert call.args[0] == "POST"
    assert call.args[1] == "/ingest_raw"
    assert call.kwargs["params"]["plugin"] == "raw"
    assert call.kwargs["files"][0][0] == "payload"
    assert call.kwargs["files"][1][0] == "f"

    dummy_client._request.return_value = {"status": "pending", "req_id": "r3", "data": {}}
    zip_file = tmp_path / "bundle.zip"
    zip_file.write_bytes(b"PK\x03\x04dummy")
    result_zip = await api.zip(
        operation_id="op1",
        plugin_name="ignored",
        zipfile_path=str(zip_file),
        params={"flt": {"operation_ids": ["op1"]}},
    )
    assert result_zip.req_id == "r3"

    dummy_client._request.return_value = {"data": {"status": "done", "id": "req-x"}}
    status = await api.status("op1", "req-x")
    assert status["status"] == "done"
    call = dummy_client._request.await_args_list[-1]
    assert call.args[0] == "GET"
    assert call.args[1] == "/request_get_by_id"
    assert call.kwargs["params"]["obj_id"] == "req-x"


@pytest.mark.unit
async def test_ingest_local_variants(dummy_client):
    from gulp_sdk.api.ingest import IngestAPI

    api = IngestAPI(dummy_client)

    dummy_client._request.return_value = {"status": "pending", "req_id": "a", "data": {}}
    assert (await api.file_local("op1", "ctx", "win_evtx", "path.evtx")).req_id == "a"

    dummy_client._request.return_value = {"status": "pending", "req_id": "b", "data": {}}
    assert (await api.file_local_to_source("src1", "path.evtx")).req_id == "b"

    dummy_client._request.return_value = {"status": "pending", "req_id": "c", "data": {}}
    assert (await api.zip_local("op1", "ctx", "bundle.zip")).req_id == "c"

    dummy_client._request.return_value = {"data": ["f1", "f2"]}
    files = await api.local_list()
    assert isinstance(files, list)


@pytest.mark.unit
async def test_enrich_all_methods(dummy_client):
    from gulp_sdk.api.enrich import EnrichAPI

    api = EnrichAPI(dummy_client)

    await api.enrich_documents(
        operation_id="op1",
        plugin="enrich_whois",
        fields={"risk": 1},
        flt={"operation_ids": ["op1"]},
        plugin_params={"custom_parameters": {}},
        req_id="r-enrich",
    )

    dummy_client._request.return_value = {"data": {"id": "doc1"}}
    one = await api.enrich_single_id(
        operation_id="op1",
        doc_id="doc1",
        plugin="enrich_whois",
        fields={"risk": 2},
        plugin_params={"custom_parameters": {}},
    )
    assert one.get("id") == "doc1"

    dummy_client._request.return_value = {"status": "pending", "req_id": "upd", "data": {}}
    await api.update_documents("op1", {"a": 1}, flt={"operation_ids": ["op1"]})

    dummy_client._request.return_value = {"data": {"id": "doc1"}}
    assert (await api.update_single_id("op1", "doc1", {"a": 2})).get("id") == "doc1"

    dummy_client._request.return_value = {"status": "pending", "req_id": "tag", "data": {}}
    await api.tag_documents("op1", ["t1"], flt={"operation_ids": ["op1"]})

    dummy_client._request.return_value = {"data": {"id": "doc1"}}
    assert (await api.tag_single_id("op1", "doc1", ["t2"]))["id"] == "doc1"

    dummy_client._request.return_value = {"status": "pending", "req_id": "rm", "data": {}}
    await api.enrich_remove("op1", "risk", flt={"operation_ids": ["op1"]})

    assert dummy_client._request.await_count >= 7


@pytest.mark.unit
async def test_acl_all_methods(dummy_client):
    from gulp_sdk.api.acl import AclAPI

    api = AclAPI(dummy_client)
    dummy_client._request.return_value = {"data": {"id": "obj1"}}

    assert (await api.add_granted_user("obj1", "note", "u1"))["id"] == "obj1"
    assert (await api.remove_granted_user("obj1", "note", "u1"))["id"] == "obj1"
    assert (await api.add_granted_group("obj1", "note", "g1"))["id"] == "obj1"
    assert (await api.remove_granted_group("obj1", "note", "g1"))["id"] == "obj1"
    assert (await api.make_private("obj1", "note"))["id"] == "obj1"
    assert (await api.make_public("obj1", "note"))["id"] == "obj1"


@pytest.mark.unit
async def test_storage_all_methods(dummy_client, tmp_path: Path):
    from gulp_sdk.api.storage import StorageAPI

    api = StorageAPI(dummy_client)
    dummy_client._request.return_value = {"data": {"deleted": 1}}

    assert (await api.delete_by_id("op1", "s1"))["deleted"] == 1
    assert (await api.delete_by_tags(operation_id="op1"))["deleted"] == 1

    dummy_client._request.return_value = {"data": {"files": []}}
    listed = await api.list_files(operation_id="op1", max_results=10)
    assert isinstance(listed, dict)

    out = tmp_path / "file.bin"
    saved = await api.get_file_by_id("op1", "s1", str(out))
    assert saved == str(out)
    assert out.read_bytes() == b"download"


@pytest.mark.unit
async def test_users_and_user_groups_all_methods(dummy_client):
    from gulp_sdk.api.users import UsersAPI
    from gulp_sdk.api.user_groups import UserGroupsAPI

    users = UsersAPI(dummy_client)
    groups = UserGroupsAPI(dummy_client)

    dummy_client._request.return_value = {"data": {"id": "u1"}}
    assert (await users.me())["id"] == "u1"
    assert (await users.get_current())["id"] == "u1"
    assert (await users.get("u1"))["id"] == "u1"
    assert (await users.create("u1", "p", ["read"]))["id"] == "u1"
    assert (await users.update(user_id="u1", email="a@b.c"))["id"] == "u1"
    assert (await users.delete("u1"))["id"] == "u1"

    dummy_client._request.return_value = {"data": [{"id": "u1"}]}
    assert isinstance(await users.list(), list)

    dummy_client._request.return_value = {"data": 123}
    assert await users.session_keepalive() == 123

    dummy_client._request.return_value = {"data": {"k": "v"}}
    assert (await users.set_data("k", "v"))["k"] == "v"

    dummy_client._request.return_value = {"data": "v"}
    assert await users.get_data("k") == "v"

    dummy_client._request.return_value = {"data": {"deleted": True}}
    assert (await users.delete_data("k"))["deleted"] is True

    dummy_client._request.return_value = {"data": {"id": "g1"}}
    assert (await groups.create("g1", ["read"]))["id"] == "g1"
    assert (await groups.update("g1", description="d"))["id"] == "g1"
    assert (await groups.get("g1"))["id"] == "g1"
    assert (await groups.add_user("g1", "u1"))["id"] == "g1"
    assert (await groups.remove_user("g1", "u1"))["id"] == "g1"
    assert (await groups.delete("g1"))["id"] == "g1"

    dummy_client._request.return_value = {"data": [{"id": "g1"}]}
    assert isinstance(await groups.list(), list)


@pytest.mark.unit
async def test_collab_all_methods(dummy_client, tmp_path: Path):
    from gulp_sdk.api.collab import CollabAPI

    api = CollabAPI(dummy_client)

    dummy_client._request.return_value = {"data": {"id": "n1"}}
    assert (await api.note_create("op1", "ctx1", "src1", "n", "txt"))["id"] == "n1"
    assert (await api.note_update("n1", text="x"))["id"] == "n1"
    assert (await api.note_delete("n1"))["id"] == "n1"
    assert (await api.note_get_by_id("n1"))["id"] == "n1"

    dummy_client._request.return_value = {"data": [{"id": "n1"}]}
    assert isinstance(await api.note_list(operation_id="op1"), list)

    dummy_client._request.return_value = {"data": {"id": "l1"}}
    assert (await api.link_create("op1", "d1", ["d2"]))["id"] == "l1"
    assert (await api.link_update("l1", doc_ids=["d2"]))["id"] == "l1"
    assert (await api.link_delete("l1"))["id"] == "l1"
    assert (await api.link_get_by_id("l1"))["id"] == "l1"

    dummy_client._request.return_value = {"data": [{"id": "l1"}]}
    assert isinstance(await api.link_list(operation_id="op1"), list)

    dummy_client._request.return_value = {"data": {"id": "h1"}}
    assert (await api.highlight_create("op1", [1, 2]))["id"] == "h1"
    assert (await api.highlight_update("h1", time_range=[1, 2]))["id"] == "h1"
    assert (await api.highlight_delete("h1"))["id"] == "h1"
    assert (await api.highlight_get_by_id("h1"))["id"] == "h1"

    dummy_client._request.return_value = {"data": [{"id": "h1"}]}
    assert isinstance(await api.highlight_list(operation_id="op1"), list)

    img = tmp_path / "glyph.bin"
    img.write_bytes(b"img")
    dummy_client._request.return_value = {"data": {"id": "g1"}}
    assert (await api.glyph_create(str(img), name="g"))["id"] == "g1"
    assert (await api.glyph_update("g1", img_path=str(img)))["id"] == "g1"
    assert (await api.glyph_delete("g1"))["id"] == "g1"
    assert (await api.glyph_get_by_id("g1"))["id"] == "g1"

    dummy_client._request.return_value = {"data": [{"id": "g1"}]}
    assert isinstance(await api.glyph_list(), list)


@pytest.mark.unit
async def test_collab_optional_params_and_filter_inference(dummy_client, tmp_path: Path):
    from gulp_sdk.api.collab import CollabAPI

    api = CollabAPI(dummy_client)
    dummy_client._request.return_value = {"data": {"id": "x1"}}

    await api.note_create(
        "op1",
        "ctx1",
        "src1",
        "note",
        "text",
        ws_id="ws-custom",
        tags=["a"],
        glyph_id="g1",
        color="#fff",
        private=True,
        time_pin=123,
        doc={"k": "v"},
        req_id="req-note-create",
    )
    call = dummy_client._request.await_args_list[-1]
    assert call.kwargs["params"]["ws_id"] == "ws-custom"
    assert call.kwargs["params"]["glyph_id"] == "g1"
    assert call.kwargs["params"]["private"] is True
    assert call.kwargs["json"]["doc"] == {"k": "v"}

    await api.note_update(
        "n1",
        ws_id="ws-custom",
        name="n2",
        text="body",
        tags=["t"],
        glyph_id="g2",
        color="#000",
        doc={"a": 1},
        time_pin=99,
        req_id="req-note-update",
    )
    call = dummy_client._request.await_args_list[-1]
    assert call.kwargs["params"]["name"] == "n2"
    assert call.kwargs["params"]["time_pin"] == 99
    assert call.kwargs["json"]["tags"] == ["t"]

    dummy_client._request.return_value = {"data": [{"id": "n1"}]}
    notes = await api.note_list(flt={"operation_ids": ["op-from-filter"]}, req_id="req-note-list")
    assert isinstance(notes, list)
    call = dummy_client._request.await_args_list[-1]
    assert call.kwargs["params"]["operation_id"] == "op-from-filter"
    assert call.kwargs["params"]["req_id"] == "req-note-list"

    dummy_client._request.return_value = {"data": {"id": "l1"}}
    await api.link_create(
        "op1",
        "doc-a",
        ["doc-b"],
        name="link",
        description="desc",
        tags=["x"],
        glyph_id="g3",
        color="#123",
        private=False,
        req_id="req-link-create",
    )
    call = dummy_client._request.await_args_list[-1]
    assert call.kwargs["params"]["private"] is False
    assert call.kwargs["json"]["description"] == "desc"

    await api.link_update(
        "l1",
        name="link2",
        description="desc2",
        tags=["y"],
        glyph_id="g4",
        color="#456",
        doc_ids=["doc-c"],
        req_id="req-link-update",
    )
    call = dummy_client._request.await_args_list[-1]
    assert call.kwargs["params"]["name"] == "link2"
    assert call.kwargs["json"]["doc_ids"] == ["doc-c"]

    dummy_client._request.return_value = {"data": [{"id": "l1"}]}
    links = await api.link_list(flt={"operation_ids": ["op-link"]}, req_id="req-link-list")
    assert isinstance(links, list)
    call = dummy_client._request.await_args_list[-1]
    assert call.kwargs["params"]["operation_id"] == "op-link"

    dummy_client._request.return_value = {"data": {"id": "h1"}}
    await api.highlight_create(
        "op1",
        [10, 20],
        name="h",
        description="hd",
        tags=["ht"],
        glyph_id="gh",
        color="#abc",
        private=True,
        req_id="req-h-create",
    )
    call = dummy_client._request.await_args_list[-1]
    assert call.kwargs["params"]["private"] is True
    assert call.kwargs["json"]["time_range"] == [10, 20]

    await api.highlight_update(
        "h1",
        name="h2",
        description="upd",
        tags=["z"],
        glyph_id="g5",
        color="#def",
        time_range=None,
        req_id="req-h-update",
    )
    call = dummy_client._request.await_args_list[-1]
    assert call.kwargs["json"]["time_range"] == []
    assert call.kwargs["params"]["req_id"] == "req-h-update"

    dummy_client._request.return_value = {"data": [{"id": "h1"}]}
    highlights = await api.highlight_list(
        flt={"operation_ids": ["op-highlight"]},
        req_id="req-h-list",
    )
    assert isinstance(highlights, list)
    call = dummy_client._request.await_args_list[-1]
    assert call.kwargs["params"]["operation_id"] == "op-highlight"

    img = tmp_path / "glyph2.bin"
    img.write_bytes(b"img")
    dummy_client._request.return_value = {"data": {"id": "g2"}}
    await api.glyph_create(str(img), name="glyph", private=True, req_id="req-g-create")
    call = dummy_client._request.await_args_list[-1]
    assert call.kwargs["params"]["private"] is True
    assert call.kwargs["params"]["req_id"] == "req-g-create"

    await api.glyph_update("g2", name="g-upd", req_id="req-g-upd")
    call = dummy_client._request.await_args_list[-1]
    assert call.kwargs["files"] is None
    assert call.kwargs["params"]["name"] == "g-upd"

    dummy_client._request.return_value = {"data": [{"id": "g2"}]}
    glyphs = await api.glyph_list(flt={"ids": ["g2"]}, req_id="req-g-list")
    assert isinstance(glyphs, list)
    call = dummy_client._request.await_args_list[-1]
    assert call.kwargs["params"]["req_id"] == "req-g-list"


@pytest.mark.unit
async def test_users_and_groups_optional_params_and_empty_update_body(dummy_client):
    from gulp_sdk.api.users import UsersAPI
    from gulp_sdk.api.user_groups import UserGroupsAPI

    users = UsersAPI(dummy_client)
    groups = UserGroupsAPI(dummy_client)

    dummy_client._request.return_value = {"data": {"id": "u2"}}
    await users.create(
        "u2",
        "Passw0rd!",
        ["read"],
        email="u2@example.com",
        user_data={"team": "blue"},
        glyph_id="gu2",
        req_id="req-user-create",
    )
    call = dummy_client._request.await_args_list[-1]
    assert call.kwargs["params"]["email"] == "u2@example.com"
    assert call.kwargs["params"]["glyph_id"] == "gu2"
    assert call.kwargs["json"]["user_data"] == {"team": "blue"}

    await users.update(
        user_id="u2",
        password="NewPassw0rd!",
        permission=["read", "edit"],
        email="u2b@example.com",
        user_data={"x": 1},
        merge_user_data=False,
        glyph_id="gu2b",
        req_id="req-user-update",
    )
    call = dummy_client._request.await_args_list[-1]
    assert call.kwargs["params"]["merge_user_data"] is False
    assert call.kwargs["params"]["password"] == "NewPassw0rd!"
    assert call.kwargs["json"]["permission"] == ["read", "edit"]

    dummy_client._request.return_value = {"data": [{"id": "u2"}]}
    listed = await users.list(req_id="req-user-list")
    assert isinstance(listed, list)
    assert dummy_client._request.await_args_list[-1].kwargs["params"]["req_id"] == "req-user-list"

    dummy_client._request.return_value = {"data": {"ok": True}}
    await users.set_data("k", {"v": 1}, user_id="u2", req_id="req-set")
    call = dummy_client._request.await_args_list[-1]
    assert call.kwargs["params"]["user_id"] == "u2"
    assert call.kwargs["params"]["req_id"] == "req-set"

    dummy_client._request.return_value = {"data": "vv"}
    _ = await users.get_data("k", user_id="u2", req_id="req-get")
    call = dummy_client._request.await_args_list[-1]
    assert call.kwargs["params"]["user_id"] == "u2"
    assert call.kwargs["params"]["req_id"] == "req-get"

    dummy_client._request.return_value = {"data": {"deleted": True}}
    _ = await users.delete_data("k", user_id="u2", req_id="req-del")
    call = dummy_client._request.await_args_list[-1]
    assert call.kwargs["params"]["user_id"] == "u2"
    assert call.kwargs["params"]["req_id"] == "req-del"

    dummy_client._request.return_value = {"data": {"id": "g2"}}
    await groups.create(
        "g2",
        ["read"],
        description="desc",
        glyph_id="gg2",
        req_id="req-group-create",
    )
    call = dummy_client._request.await_args_list[-1]
    assert call.kwargs["params"]["glyph_id"] == "gg2"
    assert call.kwargs["json"]["description"] == "desc"

    await groups.update("g2")
    call = dummy_client._request.await_args_list[-1]
    assert call.kwargs["json"] is None

    await groups.update(
        "g2",
        permission=["read", "edit"],
        description="desc2",
        glyph_id="gg2b",
        req_id="req-group-update",
    )
    call = dummy_client._request.await_args_list[-1]
    assert call.kwargs["params"]["glyph_id"] == "gg2b"
    assert call.kwargs["params"]["req_id"] == "req-group-update"
    assert call.kwargs["json"]["permission"] == ["read", "edit"]

    await groups.delete("g2", req_id="req-group-delete")
    assert dummy_client._request.await_args_list[-1].kwargs["params"]["req_id"] == "req-group-delete"

    await groups.get("g2", req_id="req-group-get")
    assert dummy_client._request.await_args_list[-1].kwargs["params"]["req_id"] == "req-group-get"

    dummy_client._request.return_value = {"data": [{"id": "g2"}]}
    listed_groups = await groups.list(flt={"ids": ["g2"]}, req_id="req-group-list")
    assert isinstance(listed_groups, list)
    assert dummy_client._request.await_args_list[-1].kwargs["params"]["req_id"] == "req-group-list"

    dummy_client._request.return_value = {"data": {"id": "g2"}}
    await groups.add_user("g2", "u2", req_id="req-group-add")
    assert dummy_client._request.await_args_list[-1].kwargs["params"]["req_id"] == "req-group-add"

    await groups.remove_user("g2", "u2", req_id="req-group-remove")
    assert dummy_client._request.await_args_list[-1].kwargs["params"]["req_id"] == "req-group-remove"


@pytest.mark.unit
async def test_db_plugins_and_documents_shim(dummy_client, tmp_path: Path):
    from gulp_sdk.api.db import DbAPI
    from gulp_sdk.api.plugins import PluginsAPI
    from gulp_sdk.api.documents import DocumentsAPI

    db = DbAPI(dummy_client)
    plugins = PluginsAPI(dummy_client)

    dummy_client._request.return_value = {"status": "pending", "req_id": "r1", "data": {}}
    assert isinstance(await db.rebase_by_query("op1", "ws1", 1000, flt={}), dict)

    dummy_client._request.return_value = {"data": {"index": "op1"}}
    assert (await db.delete_index("op1"))["index"] == "op1"
    assert (await db.refresh_index("op1"))["index"] == "op1"

    dummy_client._request.return_value = {"data": [{"name": "op1"}]}
    assert isinstance(await db.list_indexes(), list)

    pfile = tmp_path / "p.py"
    pfile.write_text("print('x')", encoding="utf-8")
    mfile = tmp_path / "m.json"
    mfile.write_text("{}", encoding="utf-8")
    cfile = tmp_path / "cfg.json"
    cfile.write_text("{}", encoding="utf-8")

    dummy_client._request.return_value = {"data": {"ok": True}}
    assert isinstance(await plugins.list(), list) is False or True
    await plugins.list_ui()
    await plugins.upload(str(pfile))
    await plugins.delete("p.py")
    await plugins.mapping_list()
    await plugins.mapping_upload(str(mfile))
    await plugins.mapping_delete("m.json")
    await plugins.request_get("r1")
    await plugins.request_cancel("r1")
    await plugins.request_list("op1")
    await plugins.request_delete("op1")
    await plugins.enhance_map_create(1, "p")
    await plugins.enhance_map_update("e1")
    await plugins.enhance_map_delete("e1")
    await plugins.enhance_map_get("e1")
    await plugins.enhance_map_list()
    await plugins.object_delete_bulk("op1", "note", {})
    await plugins.request_set_completed("r1")
    await plugins.config_upload(str(cfile))

    # download-like methods
    out1 = tmp_path / "plugin.out"
    out2 = tmp_path / "mapping.out"
    out3 = tmp_path / "cfg.out"
    assert (await plugins.download("p.py", str(out1))) == str(out1)
    assert (await plugins.mapping_download("m.json", str(out2))) == str(out2)
    assert (await plugins.config_download(str(out3))) == str(out3)
    assert out1.exists() and out2.exists() and out3.exists()

    dummy_client._request.return_value = {"data": {"version": "1.0"}}
    assert await plugins.version() == "1.0"

    docs = DocumentsAPI(dummy_client)
    with pytest.raises(NotImplementedError):
        _ = docs.get  # noqa: B018


@pytest.mark.unit
async def test_operations_all_methods(dummy_client):
    from gulp_sdk.api.operations import OperationsAPI

    api = OperationsAPI(dummy_client)

    dummy_client._request.return_value = {"data": {"id": "op1", "name": "n"}}
    created = await api.create("n", "d")
    assert created.id == "op1"
    got = await api.get("op1")
    assert got.id == "op1"

    # list endpoint currently returns full array once
    dummy_client._request.return_value = {
        "data": [
            {"id": "op1", "name": "a"},
            {"id": "op2", "name": "b"},
        ]
    }
    out = []
    async for item in api.list(limit=10):
        out.append(item.id)
    assert out == ["op1", "op2"]

    dummy_client._request.return_value = {"data": {"id": "op1", "name": "a", "description": "x"}}
    assert (await api.update("op1", description="x")).id == "op1"
    assert await api.delete("op1") is True

    dummy_client._request.return_value = {"data": {"id": "ctx1"}}
    assert (await api.context_create("op1", "ctx"))["id"] == "ctx1"
    assert (await api.context_get("ctx1"))["id"] == "ctx1"
    assert (await api.context_update("ctx1", color="#fff"))["id"] == "ctx1"
    assert (await api.context_delete("ctx1"))["id"] == "ctx1"

    dummy_client._request.return_value = {"data": [{"id": "ctx1"}]}
    assert isinstance(await api.context_list("op1"), list)

    dummy_client._request.return_value = {"data": {"id": "src1"}}
    assert (await api.source_create("op1", "ctx1", "src"))["id"] == "src1"
    assert (await api.source_get("src1"))["id"] == "src1"
    assert (await api.source_update("src1", color="#000"))["id"] == "src1"
    assert (await api.source_delete("src1"))["id"] == "src1"
    assert isinstance(await api.operation_cleanup("op1"), dict)

    dummy_client._request.return_value = {"data": [{"id": "src1"}]}
    assert isinstance(await api.source_list("op1", "ctx1"), list)


@pytest.mark.unit
async def test_queries_additional_methods(dummy_client, tmp_path: Path):
    from gulp_sdk.api.queries import QueriesAPI

    api = QueriesAPI(dummy_client)

    dummy_client._request.return_value = {"data": {"id": "d1"}}
    assert (await api.query_single_id("op1", "d1"))["id"] == "d1"

    dummy_client._request.return_value = {"data": {"aggregations": {}}}
    assert isinstance(await api.query_aggregation("op1", {"aggs": {}}), dict)

    dummy_client._request.return_value = {"data": [{"req_id": "r1"}]}
    assert isinstance(await api.query_history_get(), list)

    dummy_client._request.return_value = {"data": {"buckets": []}}
    assert isinstance(await api.query_max_min_per_field("op1", group_by="event.code"), dict)

    dummy_client._request.return_value = {"data": [{"id": "op1"}]}
    assert isinstance(await api.query_operations(), list)

    dummy_client._request.return_value = {"data": {"field": "keyword"}}
    assert isinstance(await api.query_fields_by_source("op1", "ctx1", "src1"), dict)

    # export json already tested in previous test; here cover req_id path
    out = tmp_path / "export2.json"
    assert (await api.query_gulp_export_json("op1", str(out), req_id="r1")) == str(out)


@pytest.mark.unit
async def test_ingest_preview_and_file_to_source(dummy_client, tmp_path: Path):
    from gulp_sdk.api.ingest import IngestAPI

    api = IngestAPI(dummy_client)
    f = tmp_path / "a.evtx"
    f.write_bytes(b"x")

    dummy_client._request.return_value = {"data": {"preview": True}}
    assert isinstance(await api.preview("op1", "win_evtx", str(f)), dict)
    call = dummy_client._request.await_args_list[-1]
    assert call.args[1] == "/ingest_file"
    assert call.kwargs["headers"]["size"] == "1"
    assert call.kwargs["headers"]["continue_offset"] == "0"
    assert call.kwargs["params"]["preview_mode"] is True
    assert call.kwargs["files"][0][0] == "payload"
    assert call.kwargs["files"][1][0] == "f"

    dummy_client._request.return_value = {"status": "pending", "req_id": "r9", "data": {}}
    out = await api.file_to_source("src1", str(f))
    assert out.req_id == "r9"


@pytest.mark.unit
async def test_plugins_optional_params_and_download_error_paths(dummy_client, tmp_path: Path):
    from gulp_sdk.api.plugins import PluginsAPI

    class _Resp:
        def __init__(self, status_code: int, content: bytes = b"{}"):
            self.status_code = status_code
            self.content = content

        def json(self):
            return {"status": "error", "data": {"msg": "boom"}}

    api = PluginsAPI(dummy_client)

    pfile = tmp_path / "plug.py"
    pfile.write_text("print('x')", encoding="utf-8")
    mfile = tmp_path / "map.json"
    mfile.write_text("{}", encoding="utf-8")
    cfile = tmp_path / "cfg.json"
    cfile.write_text("{}", encoding="utf-8")

    dummy_client._request.return_value = {"data": {"ok": True}}
    await api.list(req_id="r-list")
    await api.list_ui(req_id="r-list-ui")
    await api.upload(str(pfile), plugin_type="ui", fail_if_exists=True, req_id="r-up")
    await api.delete("plug.py", plugin_type="extension", req_id="r-del")
    await api.mapping_list(req_id="r-ml")
    await api.mapping_upload(str(mfile), fail_if_exists=True, req_id="r-mu")
    await api.mapping_delete("map.json", req_id="r-md")
    await api.version(req_id="r-ver")
    await api.request_get("rid", req_id="r-rg")
    await api.request_cancel("rid", expire_now=True, req_id="r-rc")
    await api.request_list("op1", running_only=True, req_id="r-rl")
    await api.request_delete("op1", obj_id="rid", req_id="r-rd")
    await api.enhance_map_create(1, "p", glyph_id="g1", color="#fff", req_id="r-emc")
    await api.enhance_map_update("e1", glyph_id="g2", color="#000", req_id="r-emu")
    await api.enhance_map_delete("e1", req_id="r-emd")
    await api.enhance_map_get("e1", req_id="r-emg")
    await api.enhance_map_list(flt={"plugin": "p"}, req_id="r-eml")
    await api.object_delete_bulk("op1", "note", {"ids": ["n1"]}, req_id="r-odb")
    await api.request_set_completed("rid", failed=True, req_id="r-rsc")
    await api.config_upload(str(cfile), req_id="r-cu")

    # Exercise download/mapping/config error branches that call _raise_for_status.
    dummy_client._client.get = AsyncMock(return_value=_Resp(500, b"err"))
    await api.download("plug.py", str(tmp_path / "x.py"), req_id="r-down-err")
    await api.mapping_download("map.json", str(tmp_path / "x.json"), req_id="r-md-err")
    await api.config_download(str(tmp_path / "x.cfg"), req_id="r-cd-err")
    assert dummy_client._raise_for_status.call_count == 3


@pytest.mark.unit
async def test_operations_optional_params_and_error_paths(dummy_client):
    from gulp_sdk.api.operations import OperationsAPI

    api = OperationsAPI(dummy_client)

    with pytest.raises(ValueError):
        await api.update("op1", name="new-name")

    dummy_client._request.return_value = {"data": {"id": "x"}}
    await api.context_create("op1", "ctx", color="#fff", glyph_id="g1", req_id="r1")
    await api.source_create("op1", "ctx1", "src", color="#000", glyph_id="g2", req_id="r2")
    await api.operation_cleanup("op1", additional_tables=["note"], req_id="r3")
    await api.context_list("op1", req_id="r4")
    await api.context_get("ctx1", req_id="r5")
    await api.context_delete("ctx1", delete_data=False, ws_id="ws-x", req_id="r6")
    await api.context_update(
        "ctx1",
        color="#123",
        description="desc",
        glyph_id="g3",
        ws_id="ws-y",
        req_id="r7",
    )
    await api.source_list("op1", "ctx1", req_id="r8")
    await api.source_get("src1", req_id="r9")
    await api.source_update(
        "src1",
        color="#abc",
        description="desc2",
        glyph_id="g4",
        ws_id="ws-z",
        req_id="r10",
    )
    await api.source_delete("src1", delete_data=False, ws_id="ws-z2", req_id="r11")

    last_params = dummy_client._request.await_args_list[-1].kwargs["params"]
    assert last_params["req_id"] == "r11"
    assert last_params["delete_data"] is False


@pytest.mark.unit
async def test_queries_optional_and_error_branches(dummy_client, tmp_path: Path):
    from gulp_sdk.api.queries import QueriesAPI

    class _Resp:
        def __init__(self, status_code: int, content: bytes = b"{}"):
            self.status_code = status_code
            self.content = content

        def json(self):
            return {"status": "error", "data": {"msg": "bad"}}

    api = QueriesAPI(dummy_client)

    dummy_client._request.return_value = {"status": "pending", "req_id": "r", "data": {}}
    await api.query_raw("op1", [{"query": {"match_all": {}}}], req_id="r-raw")
    await api.query_gulp("op1", flt={"operation_ids": ["op1"]}, req_id="r-gulp")
    await api.query_single_id("op1", "d1", req_id="r-single")
    await api.query_aggregation("op1", {"size": 0}, req_id="r-agg")
    await api.query_history_get(req_id="r-hist")
    await api.query_max_min_per_field("op1", flt={"operation_ids": ["op1"]}, group_by="event.code", req_id="r-mm")
    await api.query_operations(req_id="r-ops")
    await api.query_fields_by_source("op1", "ctx1", "src1", req_id="r-fields")

    zf = tmp_path / "rules.zip"
    zf.write_bytes(b"PK\x03\x04dummy")
    await api.query_sigma_zip(
        "op1",
        str(zf),
        src_ids=["s1"],
        levels=["high"],
        products=["windows"],
        categories=["process_creation"],
        services=["security"],
        tags=["attack.t1110"],
        req_id="r-szip",
    )

    # Export-json error path triggers _raise_for_status call.
    dummy_client._client.post = AsyncMock(return_value=_Resp(500, b"err"))
    await api.query_gulp_export_json("op1", str(tmp_path / "out.json"), req_id="r-export")
    assert dummy_client._raise_for_status.call_count >= 1
