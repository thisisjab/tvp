from datetime import datetime
from typing import Self
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from tvp.videos.constants import VideoVariantCode, VideoVariantProcessingState


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
    file_id: UUID = Field(exclude=True)
    title: str
    description: str
    is_public: bool
    duration_seconds: float | None = Field(default=None)
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


class VideoProbeDataSchema(BaseModel):
    """VideoProbeDataSchema defines the data format for storing probed video data inside redis."""  # noqa: E501

    video_id: UUID
    video_file_key: str
    width: int
    height: int
    duration_seconds: float
    fps: float
    video_bitrate: int
    # Videos with no audio have no audio bitrate (obviously)
    audio_bitrate: int | None = Field(default=None)

    @field_validator("fps", mode="before")
    @classmethod
    def proces_fps(cls: type[Self], v: str) -> float:
        if isinstance(v, int):
            return v

        if isinstance(v, str) and "/" in v:
            a, b = v.split("/")
            return int(a) / int(b)

        msg = "FPS cannot be none"
        raise ValueError(msg)


class VideoVariantSchema(BaseModel):
    """VideoVariantSchema defines the schema for VideoVariant model."""

    video_id: UUID
    variant_code: VideoVariantCode
    fps: float
    gop_size: int
    video_bitrate: int
    video_max_bitrate: int
    video_buf_size: int
    audio_bitrate: int
    audio_sample_rate: int


class CreateVideoVariantSchema(VideoVariantSchema):
    """CreateVideoVariantRequest used to request to create video variant from service."""  # noqa: E501


class GetVideoVariantSchema(BaseModel):
    """GetVideoVariantSchema is used to get video variant record from video service."""

    video_id: UUID
    variant_code: VideoVariantCode


class UpdateVideoSchema(BaseModel):
    """UpdateVideoSchema defines the schema to update videos duration and master playlist file id."""  # noqa: E501

    id: UUID
    duration_seconds: float | None = Field(default=None)
    master_playlist_file_id: UUID | None = Field(default=None)


class UpdateVariantSchema(BaseModel):
    video_id: UUID
    variant_code: VideoVariantCode
    state: VideoVariantProcessingState
    file_id: UUID | None = Field(default=None)
    playlist_file_id: UUID | None = Field(default=None)
    fps: float | None = Field(default=None)
    gop_size: int | None = Field(default=None)
    video_bitrate: int | None = Field(default=None)
    video_max_bitrate: int | None = Field(default=None)
    video_buf_size: int | None = Field(default=None)
    audio_bitrate: int | None = Field(default=None)
    audio_sample_rate: int | None = Field(default=None)
