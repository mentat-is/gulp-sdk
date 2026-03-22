"""
Data models for Gulp SDK — JSend response format and common types.

All Gulp API responses follow the JSend standard:
- status: "success" | "error" | "pending"
- timestamp_msec: server timestamp in milliseconds
- req_id: unique request identifier (UUID)
- data: payload (varies by endpoint)
"""

from dataclasses import dataclass
from enum import Enum
from typing import Any, Generic, TypeVar
from datetime import datetime

import pydantic
from pydantic import BaseModel, ConfigDict, Field


class JSendStatus(str, Enum):
    """JSend response status enum."""

    SUCCESS = "success"
    ERROR = "error"
    PENDING = "pending"


T = TypeVar("T")


@dataclass(frozen=True)
class JSendResponse(Generic[T]):
    """
    JSend-formatted response wrapper.

    All Gulp API responses follow this format with optional data payload.

    Attributes:
        status: Response status (success, error, pending)
        req_id: Unique request identifier for tracing
        timestamp_msec: Server timestamp in milliseconds
        data: Response payload (varies by endpoint)
    """

    status: JSendStatus
    req_id: str
    timestamp_msec: int
    data: T | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any], payload_type: type[T] | None = None) -> "JSendResponse[T]":
        """
        Parse a JSend response dictionary.

        Args:
            data: Dictionary containing status, req_id, timestamp_msec, data
            payload_type: Optional Pydantic model to parse data field

        Returns:
            Parsed JSendResponse

        Raises:
            ValidationError: If required fields are missing
        """
        status = data.get("status", "")
        req_id = data.get("req_id", "")
        timestamp_msec = data.get("timestamp_msec", 0)
        payload = data.get("data")

        # Parse payload if type provided
        if payload is not None and payload_type is not None:
            if isinstance(payload_type, type) and issubclass(payload_type, BaseModel):
                payload = payload_type.model_validate(payload)
            elif isinstance(payload, dict) and hasattr(payload_type, "model_validate"):
                payload = payload_type.model_validate(payload)

        return cls(
            status=JSendStatus(status),
            req_id=req_id,
            timestamp_msec=timestamp_msec,
            data=payload,
        )


# Common response models used across APIs


class User(BaseModel):
    """User account in Gulp."""

    model_config = ConfigDict(extra="allow")

    id: str = Field(..., description="Unique user ID")
    username: str = Field(..., description="Login username")
    display_name: str | None = Field(default=None, description="Display name")
    permissions: list[str] = Field(default_factory=list, description="User permissions")
    groups: list[str] = Field(default_factory=list, description="User group memberships")


class TokenSession(BaseModel):
    """Authentication token session."""

    model_config = ConfigDict(extra="allow")

    token: str = Field(..., description="Session token (UUID)")
    user_id: str = Field(..., description="Associated user ID")
    expires_at: int | datetime | None = Field(
        default=None, description="Token expiration time (epoch ms)"
    )


class Operation(BaseModel):
    """Gulp operation (document collection with metadata)."""

    model_config = ConfigDict(extra="allow")

    id: str = Field(..., description="Operation ID")
    name: str = Field(..., description="Operation name")
    description: str | None = Field(default=None, description="Operation description")
    created_at: datetime | None = Field(default=None, description="Creation timestamp")
    updated_at: datetime | None = Field(default=None, description="Last update timestamp")
    owner_id: str | None = Field(default=None, description="Owner user ID")


class GulpDocument(BaseModel):
    """Document stored in Gulp."""

    model_config = ConfigDict(extra="allow")

    id: str = Field(..., description="Document ID")
    operation_id: str = Field(..., description="Parent operation ID")
    content: str = Field(default="", description="Document text content")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Document metadata")
    created_at: datetime | None = Field(default=None, description="Creation timestamp")
    updated_at: datetime | None = Field(default=None, description="Last update timestamp")


class Note(BaseModel):
    """Collaborative note attached to a document."""

    model_config = ConfigDict(extra="allow")

    id: str = Field(..., description="Note ID")
    document_id: str = Field(..., description="Associated document ID")
    author_id: str = Field(..., description="Author user ID")
    text: str = Field(..., description="Note content")
    created_at: datetime | None = Field(default=None)
    updated_at: datetime | None = Field(default=None)


class Highlight(BaseModel):
    """Time-range highlight on a source."""

    model_config = ConfigDict(extra="allow")

    id: str = Field(..., description="Highlight ID")
    operation_id: str = Field(..., description="Parent operation ID")
    name: str | None = Field(default=None, description="Highlight name")
    description: str | None = Field(default=None, description="Description")
    color: str | None = Field(default=None, description="Color hex string")
    tags: list[str] = Field(default_factory=list, description="Tags")
    time_range: list[int] = Field(default_factory=list, description="[start_ns, end_ns]")
    owner_id: str | None = Field(default=None, description="Owner user ID")
    private: bool = Field(default=False, description="Private flag")


class Glyph(BaseModel):
    """Glyph image stored in Gulp."""

    model_config = ConfigDict(extra="allow")

    id: str = Field(..., description="Glyph ID")
    name: str | None = Field(default=None, description="Glyph name")
    owner_id: str | None = Field(default=None, description="Owner user ID")
    private: bool = Field(default=False, description="Private flag")


class UserGroup(BaseModel):
    """User group for shared permissions."""

    model_config = ConfigDict(extra="allow")

    id: str = Field(..., description="Group ID")
    name: str = Field(..., description="Group name")
    description: str | None = Field(default=None, description="Description")
    permission: list[str] = Field(default_factory=list, description="Permissions")
    user_ids: list[str] = Field(default_factory=list, description="Member user IDs")


class RequestStats(BaseModel):
    """Async request stats object."""

    model_config = ConfigDict(extra="allow")

    id: str = Field(..., description="Request ID")
    status: str = Field(..., description="Request status")
    operation_id: str | None = Field(default=None, description="Related operation ID")
    owner_id: str | None = Field(default=None, description="Owner user ID")


class PluginEntry(BaseModel):
    """Plugin metadata entry."""

    model_config = ConfigDict(extra="allow")

    filename: str = Field(..., description="Plugin filename (internal name)")
    display_name: str | None = Field(default=None, description="Display name")
    type: str | None = Field(default=None, description="Plugin type")
    version: str | None = Field(default=None, description="Plugin version")
    desc: str | None = Field(default=None, description="Description")


class MappingFile(BaseModel):
    """Mapping file metadata."""

    model_config = ConfigDict(extra="allow")

    name: str = Field(..., description="Mapping file name")
    plugin: str | None = Field(default=None, description="Associated plugin")


class EnhanceDocumentMap(BaseModel):
    """Enhance document mapping entry."""

    model_config = ConfigDict(extra="allow")

    id: str = Field(..., description="Mapping ID")
    operation_id: str | None = Field(default=None, description="Related operation ID")
    plugin: str | None = Field(default=None, description="Plugin name")


class Link(BaseModel):
    """Relationship/link between two documents."""

    model_config = ConfigDict(extra="allow")

    id: str = Field(..., description="Link ID")
    source_doc_id: str = Field(..., description="Source document ID")
    target_doc_id: str = Field(..., description="Target document ID")
    link_type: str = Field(..., description="Type of relationship")
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime | None = Field(default=None)
