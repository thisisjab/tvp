from collections.abc import Iterable
from datetime import timedelta
from typing import Protocol, Self
from uuid import UUID, uuid4

import orjson
import structlog
from orjson import JSONDecodeError
from pydantic import ValidationError
from redis.asyncio import Redis

from tvp.errors import BadRequestError, FieldsError, InternalServerError, NotFoundError
from tvp.errors.base import APIError
from tvp.files.deps import TaskiqFileServiceDep
from tvp.users.utils import create_jwt, validate_jwt
from tvp.utils.datetime import get_now
from tvp.utils.pagination import (
    PaginatedAPIResponse,
    PaginationParams,
    generate_paginated_response,
)
from tvp.videos.cache_keys import video_probe_data_cache_key
from tvp.videos.constants import VideoProcessingState
from tvp.videos.models import Video
from tvp.videos.schemas import (
    CreateVideoResponse,
    CreateVideoSchema,
    FinalizeVideoUploadSchema,
    VideoFilters,
    VideoFiltersContext,
    VideoPreSaveJWT,
    VideoProbedDataSchema,
    VideoSchema,
)
from tvp.videos.storage_keys import user_uploaded_video_storage_key
from tvp.videos.utils import run_subcommand

logger = structlog.getLogger()


class VideoRepoProtocol(Protocol):
    async def get_all(
        self: Self,
        context: VideoFiltersContext,
        filters: VideoFilters,
        pagination_params: PaginationParams,
    ) -> tuple[int, Iterable[Video]]: ...
    async def create(self: Self, video: Video) -> Video: ...
    async def update(self: Self, video: Video) -> Video: ...
    async def exists_by_id(self: Self, id_: UUID) -> bool: ...
    async def get_by_id(self: Self, id_: UUID) -> Video | None: ...


class VideoService:
    def __init__(
        self: Self,
        video_repo: VideoRepoProtocol,
        file_service: TaskiqFileServiceDep,
        redis: Redis,
    ) -> None:
        self._video_repo = video_repo
        self._file_service = file_service
        self._redis = redis

        self.ALLOWED_MIMETYPES = ["video/mp4", "video/mkv"]

    async def get_user_videos(
        self: Self,
        filters: VideoFilters,
        context: VideoFiltersContext,
        pagination_params: PaginationParams,
    ) -> PaginatedAPIResponse[VideoSchema]:
        """Get all public/private videos that is watchable by user."""
        count, videos = await self._video_repo.get_all(
            context, filters, pagination_params
        )
        videos = [VideoSchema.model_validate(v, from_attributes=True) for v in videos]
        return generate_paginated_response(videos, count, pagination_params)

    async def create_video(self: Self, req: CreateVideoSchema) -> CreateVideoResponse:
        """Create a JWT for video upload and let the upload be finalized.

        Upload is finalized when client sends back the JWT afte a successful
        upload to the storage.
        """
        expiry = timedelta(minutes=15)
        expires_at = get_now() + expiry

        # Generate video id
        video_id = uuid4()

        # Creata a JWT token containing info. about this video
        # After user finalized video uploading with this token,
        # we save the record in database.
        upload_token = create_jwt(
            VideoPreSaveJWT(
                video_id=str(video_id),
                title=req.title,
                description=req.description,
                owner_id=str(req.owner_id),
                is_public=req.is_public,
            ),
            expires_at=expires_at,
        )

        upload_url = await self._file_service.generate_temprary_upload_url(
            user_uploaded_video_storage_key(owner_id=req.owner_id, video_id=video_id),
            expiry=expiry,
        )

        return CreateVideoResponse(
            token=upload_token, upload_url=upload_url.url, expires_at=expires_at
        )

    async def finalize_video_upload(
        self: Self, req: FinalizeVideoUploadSchema
    ) -> VideoSchema:
        """Check if video file is uploaded and has correct size and mimetype and store video record."""  # noqa: E501
        token_data = validate_jwt(req.token, VideoPreSaveJWT)
        if token_data is None:
            logger.debug("video finalize upload token cannot be validated")
            raise FieldsError({"token": ["Invalid token."]})

        if token_data.owner_id != str(req.user_id):
            # Client cannot use other clients' token
            logger.debug(
                "video finalize upload token uploader_id != request user_id",
                owner_id=token_data.owner_id,
                user_id=req.user_id,
            )
            raise FieldsError({"token": ["Invalid token."]})

        # Ensure video file is uploaded and has correct size and mimetype
        try:
            await self._file_service.validate_upload(
                user_uploaded_video_storage_key(
                    owner_id=token_data.owner_id, video_id=token_data.video_id
                ),
                expected_mimetypes=["video/mp4", "video/mpv"],
                max_size_bytes=1 * 1024 * 1024 * 1024,  # 1 Gigabyte
            )
        except APIError as e:
            if e.code == "UPLOADED_FILE_DOES_NOT_EXIST":
                msg = "File is not uploaded."
            if e.code == "UPLOADED_FILE_HAS_WRONG_SIZE":
                msg = "Uploaded size exceeds max upload size."
            if e.code == "UPLOADED_FILE_HAS_WRONG_MIMETYPE":
                msg = "Uploaded file is not a video."

            raise BadRequestError(msg) from e

        # Everything is good to go: let's store in database
        video = await self._video_repo.create(
            Video(
                id=UUID(token_data.video_id),
                title=token_data.title,
                description=token_data.description,
                is_public=token_data.is_public,
                owner_id=UUID(token_data.owner_id),
                state=VideoProcessingState.NOT_STARTED,
            )
        )

        # Spawn the processing task
        from tvp.videos.tasks import create_processing_jobs  # noqa: PLC0415

        await create_processing_jobs.kiq(video.id)  # ty:ignore[no-matching-overload]

        return VideoSchema.model_validate(video, from_attributes=True)

    async def update_video_state(
        self: Self, video_id: UUID, state: VideoProcessingState
    ) -> None:
        """Update video state if it exists."""
        video = await self._video_repo.get_by_id(video_id)
        if not video:
            raise NotFoundError

        video.state = state

        await self._video_repo.update(video)

    async def get_by_id(self: Self, id_: UUID) -> VideoSchema | None:
        """Get video by id and generate a token for master playlist if exists."""
        v = await self._video_repo.get_by_id(id_)

        if not v:
            return None

        # TODO: add master playlist logic

        return VideoSchema.model_validate(v, from_attributes=True)

    async def get_video_probed_data(
        self: Self, video_id: UUID
    ) -> VideoProbedDataSchema:
        """Get vided probed data from redis or create if not exists."""
        video = await self._video_repo.get_by_id(video_id)
        if not video:
            raise NotFoundError

        cache_key = video_probe_data_cache_key(video_id=video_id)
        probe_data = await self._redis.get(cache_key)

        try:
            probe_data = VideoProbedDataSchema.model_validate_json(probe_data)
        except ValidationError:
            probe_data = await self._probe_video(video)
            await self._redis.set(
                cache_key, probe_data.model_dump_json(), ex=timedelta(days=1)
            )

        return probe_data

    async def _probe_video(self: Self, video: Video) -> VideoProbedDataSchema:
        """Probe video data using ffprobe and returned cleaned version."""
        video_download_url = await self._file_service.get_download_link(
            user_uploaded_video_storage_key(video_id=video.id, owner_id=video.owner_id)
        )

        # Get output of ffprobe in JSON format
        probing_result = await run_subcommand(
            [
                "ffprobe",
                "-v",
                "quiet",
                "-print_format",
                "json",
                "-show_streams",
                video_download_url,
            ],
        )

        if not probing_result or probing_result.return_code != 0:
            logger.error(
                "probing viedo failed", video_id=video.id, result=probing_result
            )
            msg = "Probing video faild."
            raise InternalServerError(msg)

        # ffprobe output is in JSON
        # TODO: use pydantic objecst for parsing ffmpeg output -> This way we are sure of output format  # noqa: E501
        try:
            streams = orjson.loads(probing_result.stdout).get("streams", [])
        except JSONDecodeError as e:
            logger.exception(
                "couldn't parse json output for ffprobe",
                video_id=video.id,
                stdout=probing_result.stdout,
                exc_info=e,
            )
            msg = "Parsing video probe data failed."
            raise InternalServerError(msg) from e

        # Check there are video streams
        if not streams or streams[0].get("codec_type", "unknown") != "video":
            logger.error(
                "video has no streams or first stream is not of type video",
                video_id=video.id,
                streams=streams,
                stdout=probing_result.stdout,
            )
            msg = "Video has no valid streams."
            raise InternalServerError(msg)

        # Clean up
        video_stream = streams[0]
        probe_data = VideoProbedDataSchema(
            video_id=video.id,
            width=video_stream.get("width", 0),
            height=video_stream.get("height", 0),
            duration_seconds=video_stream.get("duration", 0),
            # r_frame_rate is in form of x/y where x and y are integers
            # Schema class will handle conversion automatically
            fps=video_stream.get("r_frame_rate", 0),
            video_bitrate=int(video_stream.get("bit_rate", 0)),
        )

        # Find first audio stream to get its bitrate
        audio_streams = [
            s for s in streams[1:] if s.get("codec_type", "unknown") == "audio"
        ]
        if audio_streams:
            probe_data.audio_bitrate = int(audio_streams[0].get("bit_rate", 0))

        return probe_data
