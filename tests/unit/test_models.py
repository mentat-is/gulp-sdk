"""Unit tests for models and response parsing."""

import pytest
from pydantic import ValidationError
from gulp_sdk.models import (
    User,
    Operation,
    GulpDocument,
    Note,
    Link,
    JSendResponse,
    JSendStatus,
)


@pytest.mark.unit
async def test_user_model():
    """Test User model validation."""
    user_data = {
        "id": "user-123",
        "username": "testuser",
        "display_name": "Test User",
        "permissions": ["READ", "EDIT"],
        "groups": ["analysts"],
    }

    user = User.model_validate(user_data)
    assert user.id == "user-123"
    assert user.username == "testuser"
    assert "READ" in user.permissions


@pytest.mark.unit
async def test_operation_model():
    """Test Operation model."""
    op_data = {
        "id": "op-123",
        "name": "Test Operation",
        "description": "Test description",
        "owner_id": "user-123",
    }

    op = Operation.model_validate(op_data)
    assert op.id == "op-123"
    assert op.name == "Test Operation"


@pytest.mark.unit
async def test_document_model():
    """Test GulpDocument model."""
    doc_data = {
        "id": "doc-123",
        "operation_id": "op-123",
        "content": "Document content",
        "metadata": {"source": "evtx", "event_id": 4688},
    }

    doc = GulpDocument.model_validate(doc_data)
    assert doc.id == "doc-123"
    assert doc.content == "Document content"
    assert doc.metadata["source"] == "evtx"


@pytest.mark.unit
async def test_jsend_response_success():
    """Test JSendResponse for success status."""
    response_dict = {
        "status": "success",
        "req_id": "req-123",
        "timestamp_msec": 1234567890,
        "data": {"id": "op-123", "name": "My Op"},
    }

    response = JSendResponse.from_dict(response_dict, Operation)
    assert response.status == JSendStatus.SUCCESS
    assert response.req_id == "req-123"
    assert isinstance(response.data, Operation)
    assert response.data.id == "op-123"


@pytest.mark.unit
async def test_jsend_response_error():
    """Test JSendResponse for error status."""
    response_dict = {
        "status": "error",
        "req_id": "req-456",
        "timestamp_msec": 1234567890,
        "data": "Not found",
    }

    response = JSendResponse.from_dict(response_dict)
    assert response.status == JSendStatus.ERROR
    assert response.data == "Not found"


@pytest.mark.unit
async def test_jsend_response_pending():
    """Test JSendResponse for pending status."""
    response_dict = {
        "status": "pending",
        "req_id": "req-789",
        "timestamp_msec": 1234567890,
        "data": {"progress": 45},
    }

    response = JSendResponse.from_dict(response_dict)
    assert response.status == JSendStatus.PENDING
    assert response.data["progress"] == 45


@pytest.mark.unit
async def test_note_model():
    """Test Note model."""
    note_data = {
        "id": "note-123",
        "document_id": "doc-123",
        "author_id": "user-123",
        "text": "This is important",
    }

    note = Note.model_validate(note_data)
    assert note.id == "note-123"
    assert note.text == "This is important"


@pytest.mark.unit
async def test_link_model():
    """Test Link model."""
    link_data = {
        "id": "link-123",
        "source_doc_id": "doc-1",
        "target_doc_id": "doc-2",
        "link_type": "related_to",
        "metadata": {"confidence": 0.95},
    }

    link = Link.model_validate(link_data)
    assert link.source_doc_id == "doc-1"
    assert link.target_doc_id == "doc-2"
    assert link.metadata["confidence"] == 0.95


@pytest.mark.unit
async def test_model_validation_error():
    """Test model validation error on missing required field."""
    # Missing required 'id' field
    invalid_op = {"name": "Test"}

    with pytest.raises(ValidationError):
        Operation.model_validate(invalid_op)
