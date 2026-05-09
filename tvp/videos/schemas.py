from datetime import datetime
from typing import Self
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from tvp.videos.constants import VideoProcessingState, VideoVariantCode


class VideoPreSaveJWT(BaseModel):
    """
    VideoPreSaveJWT is to store video info in JWT token which will be later
    used to confirm upload and create video record in database.
    """  # noqa: D205

    video_id: str
    owner_id: str
    title: str
    description: str | None
    is_public: bool


class VideoSchema(BaseModel):
    """VideoSchema defines the schema of a video object."""

    id: UUID
    owner_id: UUID
    state: VideoProcessingState
    title: str
    description: str
    is_public: bool
    duration_seconds: float | None = Field(default=None)
    master_playlist_url: str | None = Field(default=None)
    created_at: datetime


class CreateVideoSchema(BaseModel):
    """CreateVideoSchema defines the schema for creating video in the service."""

    owner_id: UUID
    title: str = Field(max_length=150)
    description: str | None = Field(default=None)
    is_public: bool


class CreateVideoRequest(BaseModel):
    """CreateVideoRequest defines the request schema for creating a video."""

    title: str = Field(max_length=150)
    description: str | None = Field(default=None)
    is_public: bool


class CreateVideoResponse(BaseModel):
    """CreateVideoResponse defines the response schema for creating a video.

    Client uploads video to given upload url, then finalizes the upload using
    the token.
    """

    token: str
    upload_url: str
    expires_at: datetime


class FinalizeVideoUploadSchema(BaseModel):
    """FinalizeVideoUploadSchema is service schema to indicate uploading video is done.

    Therefore after validation video should be saved in database.
    """

    user_id: UUID
    token: str


class FinalizeVideoUploadRequest(BaseModel):
    """FinalizeVideoUploadRequest defines the request schema for finalizing video upload."""  # noqa: E501

    token: str


class VideoProbedDataSchema(BaseModel):
    """VideoProbedDataSchema defines the data format for storing probed video data inside redis."""  # noqa: E501

    video_id: UUID
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


class VideoTranscodingJobSchema(BaseModel):
    """VideoTranscodingJobSchema defines the input schema for video trasncoding jobs."""

    video_id: UUID
    variant_code: VideoVariantCode
    fps: float
    gop_size: int
    video_bitrate: int
    video_max_bitrate: int
    video_buf_size: int
    audio_bitrate: int
    audio_sample_rate: int
