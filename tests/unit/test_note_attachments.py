"""SDK wrappers and models for note attachments."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest


@pytest.mark.unit
@pytest.mark.asyncio
async def test_note_attachment_sdk_wrappers(tmp_path):
    from gulp_sdk.api.collab import CollabAPI

    response = SimpleNamespace(status_code=200, content=b"download", json=lambda: {})
    client = SimpleNamespace(
        ws_id="ws-a",
        token="token-a",
        _request=AsyncMock(),
        _raise_for_status=Mock(),
        _client=SimpleNamespace(get=AsyncMock(return_value=response)),
    )
    api = CollabAPI(client)
    upload = tmp_path / "evidence.txt"
    upload.write_bytes(b"evidence")

    client._request.return_value = {"data": {"id": "attachment-a"}}
    created = await api.note_add_attachment(
        "note-a",
        str(upload),
        title="Evidence",
        mime_type="text/custom",
        req_id="req-add",
    )
    print("SDK attachment add response:", created)
    call = client._request.await_args
    assert call.args == ("POST", "/note_add_attachment")
    assert call.kwargs["params"] == {
        "obj_id": "note-a",
        "ws_id": "ws-a",
        "title": "Evidence",
        "mime_type": "text/custom",
        "req_id": "req-add",
    }
    assert call.kwargs["files"]["attachment"][0] == "evidence.txt"
    assert call.kwargs["files"]["attachment"][2] == "text/custom"

    client._request.return_value = {"data": [{"id": "attachment-a"}]}
    assert await api.note_list_attachments("note-a") == [{"id": "attachment-a"}]
    assert client._request.await_args.args == ("GET", "/note_list_attachments")

    client._request.return_value = {"data": {"id": "attachment-a", "note_id": "note-a"}}
    assert (await api.note_delete_attachment("note-a", "attachment-a"))["id"] == "attachment-a"
    assert client._request.await_args.args == ("DELETE", "/note_delete_attachment")

    output = tmp_path / "download.bin"
    assert await api.note_get_attachment(
        "note-a", "attachment-a", str(output), req_id="req-get"
    ) == str(output)
    assert output.read_bytes() == b"download"
    client._client.get.assert_awaited_once_with(
        "/note_get_attachment",
        params={
            "obj_id": "note-a",
            "attachment_id": "attachment-a",
            "req_id": "req-get",
        },
        headers={"token": "token-a"},
    )


@pytest.mark.unit
def test_note_attachment_sdk_model():
    from gulp_sdk import NoteAttachment

    attachment = NoteAttachment.model_validate(
        {
            "id": "attachment-a",
            "note_id": "note-a",
            "user_id": "user-a",
            "operation_id": "op-a",
            "title": "evidence.bin",
            "description": "",
            "mime_type": "application/octet-stream",
        }
    )
    assert attachment.id == "attachment-a"
    assert attachment.mime_type == "application/octet-stream"
