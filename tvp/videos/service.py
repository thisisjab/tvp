from typing import Protocol, Self
from uuid import UUID

from redis.asyncio import Redis

from tvp.errors import BadRequestError, FieldsError, NotFoundError
from tvp.files.schemas import FileSchema
from tvp.videos.constants import VideoVariantCode, VideoVariantProcessingState
from tvp.videos.models import Video, VideoVariant
from tvp.videos.schemas import (
    CreateVideoSchema,
    CreateVideoVariantSchema,
    GetVideoVariantSchema,
    UpdateVariantSchema,
    UpdateVideoSchema,
    VideoSchema,
    VideoVariantSchema,
)


class FileServiceProtocol(Protocol):
    async def get_by_id(self: Self, id_: UUID) -> FileSchema | None: ...


class VideoRepoProtocol(Protocol):
    async def create(self: Self, video: Video) -> Video: ...
    async def update(self: Self, video: Video) -> Video: ...
    async def exists_by_file_id(self: Self, file_id: UUID) -> bool: ...
    async def get_by_id(self: Self, id_: UUID) -> Video | None: ...


class VideoVariantRepoProtocol(Protocol):
    async def create(self: Self, variant: VideoVariant) -> VideoVariant: ...
    async def update(self: Self, variant: VideoVariant) -> VideoVariant: ...
    async def get_by_video_id_and_code(
        self: Self, video_id: UUID, variant_code: VideoVariantCode
    ) -> VideoVariant | None: ...


class VideoService:
    def __init__(
        self: Self,
        video_repo: VideoRepoProtocol,
        video_variant_repo: VideoVariantRepoProtocol,
        file_service: FileServiceProtocol,
        redis: Redis,
    ) -> None:
        self._video_repo = video_repo
        self._video_variant_repo = video_variant_repo
        self._file_service = file_service
        self._redis = redis

        self.ALLOWED_MIMETYPES = ["video/mp4", "video/mkv"]

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
                is_public=req.is_public,
                duration_seconds=None,
                master_playlist_file_id=None,
            )
        )

        # TODO: remove circular import
        from tvp.videos.tasks import probe_video  # noqa: PLC0415

        await probe_video.kiq(video.id)  # ty:ignore[no-matching-overload]

        return VideoSchema.model_validate(video, from_attributes=True)

    async def get_by_id(self: Self, id_: UUID) -> VideoSchema | None:
        """Get video by id and generate a token for master playlist if exists."""
        v = await self._video_repo.get_by_id(id_)

        if not v:
            return None

        # TODO: add master playlist logic

        return VideoSchema.model_validate(v, from_attributes=True)

    async def create_empty_variant(
        self: Self, req: CreateVideoVariantSchema
    ) -> VideoVariantSchema:
        """Create empty variant for video."""
        variant = await self._video_variant_repo.get_by_video_id_and_code(
            video_id=req.video_id,
            variant_code=req.variant_code,
        )

        if variant:
            msg = "Already exists."
            raise BadRequestError(msg)

        variant = await self._video_variant_repo.create(
            VideoVariant(
                state=VideoVariantProcessingState.PROCESSING_NOT_STARTED,
                video_id=req.video_id,
                variant_code=req.variant_code,
                fps=req.fps,
                gop_size=req.gop_size,
                video_bitrate=req.video_bitrate,
                video_buf_size=req.video_buf_size,
                video_max_bitrate=req.video_max_bitrate,
                audio_bitrate=req.audio_bitrate,
                audio_sample_rate=req.audio_sample_rate,
                file_id=None,
                playlist_file_id=None,
            )
        )

        return VideoVariantSchema.model_validate(variant, from_attributes=True)

    async def update(self: Self, req: UpdateVideoSchema) -> VideoSchema:
        """Update video's duration and master playlist file id."""
        video = await self._video_repo.get_by_id(req.id)

        if not video:
            raise NotFoundError

        data = req.model_dump(exclude_unset=True)

        if "master_playlist_file_id" in data:
            if (
                req.master_playlist_file_id is not None
                and await self._file_service.get_by_id(req.master_playlist_file_id)
                is None
            ):
                raise FieldsError({"master_playlist_file_id": ["Not found."]})

            video.master_playlist_file_id = req.master_playlist_file_id

        if "duration_seconds" in data:
            video.duration_seconds = req.duration_seconds

        video = await self._video_repo.update(video)
        return VideoSchema.model_validate(video, from_attributes=True)

    async def get_variant(
        self: Self, req: GetVideoVariantSchema
    ) -> VideoVariantSchema | None:
        """Get specific variant for given video."""
        variant = await self._video_variant_repo.get_by_video_id_and_code(
            req.video_id, req.variant_code
        )

        if not variant:
            return None

        return VideoVariantSchema.model_validate(variant, from_attributes=True)

    async def update_variant(
        self: Self, req: UpdateVariantSchema
    ) -> VideoVariantSchema:
        """Update video variant fields.

        For simplicity, we don't check for states right now.
        """
        variant = await self._video_variant_repo.get_by_video_id_and_code(
            req.video_id, req.variant_code
        )

        if not variant:
            raise NotFoundError

        data = req.model_dump(exclude_unset=True)
        for k in data:
            setattr(variant, k, data[k])

        variant = await self._video_variant_repo.update(variant)

        return VideoVariantSchema.model_validate(variant, from_attributes=True)
