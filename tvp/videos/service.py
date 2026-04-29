from typing import Protocol, Self
from uuid import UUID

from redis.asyncio import Redis

from tvp.errors import BadRequestError, FieldsError
from tvp.files.schemas import FileSchema
from tvp.videos.models import Video
from tvp.videos.schemas import CreateVideoSchema, VideoSchema


class FileServiceProtocol(Protocol):
    async def get_by_id(self: Self, id_: UUID) -> FileSchema | None: ...


class VideoRepoProtocol(Protocol):
    async def create(self: Self, video: Video) -> Video: ...
    async def update(self: Self, video: Video) -> Video: ...
    async def exists_by_file_id(self: Self, file_id: UUID) -> bool: ...


class VideoService:
    def __init__(
        self: Self,
        video_repo: VideoRepoProtocol,
        file_service: FileServiceProtocol,
        redis: Redis,
    ) -> None:
        self._video_repo = video_repo
        self._file_service = file_service
        self._redis = redis

        self.ALLOWED_MIMETYPES = ["vidoe/mp4", "video/mkv"]

    async def create_video(self: Self, req: CreateVideoSchema) -> VideoSchema:
        # Each file can be used to create exactly one video.
        if await self._video_repo.exists_by_file_id(req.file_id):
            msg = "Video file ID is not unique."
            raise BadRequestError(
                msg,
            )

        # Get file and validate mimetype and ownership
        file = await self._file_service.get_by_id(req.file_id)

        if not file or file.uploader_id != req.owner_id:
            raise FieldsError(
                {
                    "file_id": ["File is removed or does not exist."],
                }
            )

        if file.mimetype not in self.ALLOWED_MIMETYPES:
            msg = "This file cannot be processed due to incompatible mimetype."
            raise BadRequestError(
                msg,
            )

        # Create video in database
        video = await self._video_repo.create(
            Video(
                file_id=req.file_id,
                title=req.title,
                description=req.description,
                owner_id=req.owner_id,
                is_processed_for_streaming=False,
                is_public=req.is_public,
                total_seconds=0,
            )
        )

        # TODO: spawn video info probing taks

        return VideoSchema.model_validate(video, from_attributes=True)
