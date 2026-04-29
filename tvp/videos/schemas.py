from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class VideoMasterPlaylist(BaseModel):
    """VideoMasterPlaylist defines the schema for master playlist of a video.

    Clients must include `access_token` in every request to objects (playlists, chunks)
    inside `Authorization` header as bearer token.
    """

    access_token: str
    url: str


class VideoSchema(BaseModel):
    """VideoSchema defines the schema of a video object."""

    id: UUID
    owner_id: UUID
    title: str
    description: str
    is_public: bool
    is_processed_for_streaming: bool = Field(default=False)
    total_seconds: int | None = Field(default=None)
    master_playlist: VideoMasterPlaylist | None = Field(default=None)
    created_at: datetime


class CreateVideoSchema(BaseModel):
    """CreateVideoSchema defines the schema for creating video in the service."""

    file_id: UUID
    owner_id: UUID
    title: str = Field(max_length=150)
    description: str | None = Field(default=None)
    is_public: bool


class CreateVideoRequest(BaseModel):
    """CreateVideoRequest defines the request schema for creating a video."""

    file_id: UUID
    title: str = Field(max_length=150)
    description: str | None = Field(default=None)
    is_public: bool


class CreateVideoResponse(VideoSchema):
    """CreateVideoResponse defines the response schema for creating a video."""
