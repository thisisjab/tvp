import asyncio
import tempfile
from typing import TYPE_CHECKING
from uuid import UUID

import orjson
import structlog
from minio.datatypes import JSONDecodeError

import tvp.videos.cache_keys
from tvp.errors import InternalServerError
from tvp.files.deps import TaskiqFileServiceDep
from tvp.files.schemas import DirectPathUploadSchema
from tvp.redis.deps import TaskiqRedisClient
from tvp.taskiq import broker
from tvp.utils.redis import RedisLock
from tvp.videos.cache_keys import (
    lock_video_remaining_processing_jobs_count,
    video_remaining_processing_jobs_count,
)
from tvp.videos.constants import (
    AUDIO_BITRATES,
    HIGHEST_RESOLUTION_SUPPORTED,
    MAX_ALLOWED_FPS,
    SEGMENT_LENGTH_SECONDS,
    VIDEO_BITRATES,
    VideoVariantCode,
    VideoVariantProcessingState,
)
from tvp.videos.deps import TaskiqVideoServiceDep
from tvp.videos.schemas import (
    CreateVideoVariantSchema,
    GetVideoVariantSchema,
    UpdateVariantSchema,
    UpdateVideoSchema,
    VideoProbeDataSchema,
    VideoSchema,
)
from tvp.videos.storage_keys import video_variant_storage_key

if TYPE_CHECKING:
    from tvp.files.schemas import FileSchema

logger = structlog.getLogger(__name__)


@broker.task
async def create_master_playlist(
    video_id: UUID,
    video_service: TaskiqVideoServiceDep,
    file_service: TaskiqFileServiceDep,
    redis: TaskiqRedisClient,
) -> None:
    """Check if there are no remaining tasks and start creating segments."""
    video = await video_service.get_by_id(video_id)
    if not video:
        logger.error(
            "attempt to create master playlist with non existing video",
            video_id=video_id,
        )
        return

    async with RedisLock(
        redis, lock_video_remaining_processing_jobs_count(video_id=video_id)
    ):
        remaining_jobs = await redis.get(
            video_remaining_processing_jobs_count(video_id=video_id)
        )

        if remaining_jobs != "0":
            logger.info(
                "video is not ready to create hls playlist. skipping",
                video_id=video_id,
                remaining_jobs=remaining_jobs,
            )
            return

    variants = await video_service.get_variants_by_video_id(video_id)
    if not variants:
        logger.error(
            "attempt to create master playlist for a video with no variant",
            video_id=video_id,
        )
        return

    # Download varients
    with tempfile.TemporaryDirectory(delete=False) as working_dir:
        generated_fmp4s = []

        for v in variants:
            if v.file_id is None:
                logger.error(
                    "attempted to create fmp4 for variant without a file_id",
                    video_id=video_id,
                    variant_code=v.variant_code,
                )
                return

            # Update status
            await video_service.update_variant(
                UpdateVariantSchema(
                    video_id=video_id,
                    variant_code=v.variant_code,
                    state=VideoVariantProcessingState.MUXING,
                )
            )

            # Download file
            fmp4_src_path = f"{working_dir}/{v.variant_code.value}.mp4"
            fmp4_out_path = f"{working_dir}/f_{v.variant_code.value}.mp4"
            await file_service.download_to_path(
                v.file_id,
                fmp4_src_path,
            )

            logger.debug(
                "video variant downloaded", video_id=video_id, path=fmp4_src_path
            )

            process = await asyncio.create_subprocess_exec(
                "mp4fragment",
                fmp4_src_path,
                fmp4_out_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await process.communicate()
            if process.returncode != 0:
                logger.error(
                    "cannot create fmp4",
                    video_id=video_id,
                    variant_code=v.variant_code,
                    stdout=stdout.decode(),
                    stderr=stderr.decode(),
                )
                msg = "Cannot create fmp4."
                raise InternalServerError(msg)

            generated_fmp4s.append(fmp4_out_path)
            logger.info(
                "finished creating fmp4",
                video_id=video_id,
                variant_code=v.variant_code,
            )

        # Create playlists
        hls_output_dir = f"{working_dir}/hls/"
        process = await asyncio.create_subprocess_exec(
            "mp4hls",
            f"--segment-duration={SEGMENT_LENGTH_SECONDS}",
            f"--output-dir={hls_output_dir}",
            *generated_fmp4s,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()
        if process.returncode != 0:
            logger.error(
                "cannot package to hls",
                video_id=video_id,
                stdout=stdout.decode(),
                stderr=stderr.decode(),
            )

            await asyncio.gather(
                *[
                    video_service.update_variant(
                        UpdateVariantSchema(
                            video_id=video_id,
                            variant_code=v.variant_code,
                            state=VideoVariantProcessingState.MUXING_FAILED,
                        )
                    )
                    for v in variants
                ]
            )

            raise InternalServerError

        logger.info("muxing done :)", video_id=video_id)


@broker.task
async def process_variant(
    video_id: UUID,
    variant_code: VideoVariantCode,
    video_service: TaskiqVideoServiceDep,
    file_service: TaskiqFileServiceDep,
    redis: TaskiqRedisClient,
) -> None:
    """Transcode video to mp4, store in storage, and fire muxing job.

    For more info., visit probe_video task.
    """
    # Fetch varient
    video_variant = await video_service.get_variant(
        GetVideoVariantSchema(video_id=video_id, variant_code=variant_code)
    )

    if not video_variant:
        logger.error(
            "attempt to process a non-existing variant",
            video_id=video_id,
            variant_code=variant_code,
        )
        return

    # Get video
    video: VideoSchema = await video_service.get_by_id(video_id)  # ty:ignore[invalid-assignment]

    # Get file
    video_file: FileSchema = await file_service.get_by_id(video.file_id)  # ty:ignore[invalid-assignment]

    # Set variant status to PROCESSING
    logger.info(
        "setting video variant state",
        video_id=video_id,
        variant_code=variant_code,
        state=VideoVariantProcessingState.PROCESSING,
    )

    # TODO: this can happen in probe_video task
    await video_service.update_variant(
        UpdateVariantSchema(
            video_id=video_id,
            variant_code=variant_code,
            state=VideoVariantProcessingState.PROCESSING,
            fps=video_variant.fps,
            gop_size=video_variant.gop_size,
            video_bitrate=video_variant.audio_bitrate,
            video_max_bitrate=video_variant.video_max_bitrate,
            video_buf_size=video_variant.video_buf_size,
            audio_bitrate=video_variant.audio_bitrate,
            audio_sample_rate=video_variant.audio_sample_rate,
        )
    )

    with tempfile.TemporaryDirectory(delete=True) as output_dir:
        output_name = f"output-{variant_code.value}.mp4"
        output_path = f"{output_dir}/{output_name}"
        video_params = [
            "-vf",
            f"fps={video_variant.fps},scale=-2:{video_variant.variant_code.value}",
            "-c:v",
            "libx264",
            "-b:v",
            str(video_variant.video_bitrate),
            "-maxrate",
            str(video_variant.video_max_bitrate),
            "-bufsize",
            str(video_variant.video_buf_size),
            "-g",
            str(video_variant.gop_size),
            "-keyint_min",
            str(video_variant.gop_size),
            "-sc_threshold",
            "0",
        ]
        audio_params = (
            [
                "-c:a",
                "aac",
                "-b:a",
                str(video_variant.audio_bitrate),
                "-ar",
                str(video_variant.audio_sample_rate),
            ]
            if video_variant.audio_bitrate != 0
            else []
        )

        command = [
            "ffmpeg",
            "-i",
            video_file.url,
            *video_params,
            *audio_params,
            "-movflags",
            "frag_keyframe+empty_moov+default_base_moof",
            "-f",
            "mp4",
            output_path,
        ]

        # TODO: add timeouts
        process = await asyncio.create_subprocess_exec(
            *command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        stdout, stderr = await process.communicate()
        if process.returncode != 0:
            logger.error(
                "probing video failed",
                video_id=video_id,
                returncode=process.returncode,
                stdout=stdout.decode() if stdout else "No stdout output",
                stderr=stderr.decode() if stderr else "No stderr output",
            )
            msg = "Probing video failed."
            raise InternalServerError(msg)

        # Upload processed variant
        logger.info("uploading variant", video_id=video_id, variant_code=variant_code)
        variant_file: FileSchema = await file_service.direct_path_upload(
            DirectPathUploadSchema(
                file_path=output_path,
                name=output_name,
                key=video_variant_storage_key(video_id, variant_code),
                uploader_id=video.owner_id,
            )
        )  # ty:ignore[invalid-assignment]

        # Decrease number of remaining jobs
        async with RedisLock(
            redis, lock_video_remaining_processing_jobs_count(video_id=video_id)
        ):
            await redis.incrby(
                tvp.videos.cache_keys.video_remaining_processing_jobs_count(
                    video_id=video_id
                ),
                -1,
            )

        # Update state
        await video_service.update_variant(
            UpdateVariantSchema(
                video_id=video_id,
                variant_code=variant_code,
                state=VideoVariantProcessingState.MUXING_NOT_STARTED,
                file_id=variant_file.id,
            )
        )

        await create_master_playlist.kiq(video_id)  # ty:ignore[no-matching-overload]


async def create_processing_jobs_for_video(
    probe_data: VideoProbeDataSchema,
) -> list[CreateVideoVariantSchema]:
    """Check what variants can the video be transcoded to and create jobs."""
    # Calculate FPS
    fps = min(probe_data.fps, MAX_ALLOWED_FPS)

    # GOP size
    gop_size = round(fps * SEGMENT_LENGTH_SECONDS)

    # Select all possbile variants for video
    # Suppose if HIGHEST_RESOLUTION_SUPPORTED is 1080, LOWEST_RESOLUTION_SUPPORTED
    # is 480, and video height = 800, then variants will be [720, 480].
    variants = [
        v
        for v in VideoVariantCode
        if (
            (v.value <= HIGHEST_RESOLUTION_SUPPORTED.value)
            and (v.value <= probe_data.height)
        )
    ]

    # Create jobs for each varient
    result = []
    for v in variants:
        video_bitrate = int(
            min(
                (probe_data.video_bitrate * (v.value / probe_data.height)),
                VIDEO_BITRATES[v],
            )
        )

        audio_bitrate = min(
            probe_data.audio_bitrate or 0,
            AUDIO_BITRATES[v],
        )

        result.append(
            CreateVideoVariantSchema(
                video_id=probe_data.video_id,
                variant_code=v,
                fps=fps,
                gop_size=gop_size,
                video_bitrate=video_bitrate,
                video_max_bitrate=int(video_bitrate * 1.5),  # Industry standard
                video_buf_size=video_bitrate * 2,  # Industry standard
                audio_bitrate=audio_bitrate,
                audio_sample_rate=48000,
            )
        )

    return result


@broker.task(retry_on_error=True, max_retries=3)
async def probe_video(
    video_id: UUID,
    video_service: TaskiqVideoServiceDep,
    file_service: TaskiqFileServiceDep,
    redis: TaskiqRedisClient,
) -> None:
    """Extract video metadata using ffprobe and create variant records.

    Called after video upload completes. Probes the original video file to extract
    duration, codec, bitrate, resolution, and fps. Uses this data to determine
    which variants (1080p, 720p, etc.) should be created. Creates VideoVariant
    records with state=NOT_STARTED and queues individual processing tasks.

    Flow:
        1. Fetch Video record and original file_id
        2. Run ffprobe on the file
        3. Calculate target variants based on source resolution
        4. Insert VideoVariant records with code, fps, bitrates
        5. Queue process_variant task for each variant
        6. Update Video.duration

    Failure handling:
        - If ffprobe fails → retry with exponential backoff (max 3)
        - If variant creation fails → no tasks queued, video stays unprocessed
        - Dead letter queue for manual inspection after retries
    """
    video = await video_service.get_by_id(video_id)
    if not video:
        # Video is removed before getting chance to be processed. So let's just return.
        logger.error(
            "attempted to process a video that does not exist", video_id=video_id
        )
        return

    video_file: FileSchema = await file_service.get_by_id(video.file_id)  # ty:ignore[invalid-assignment]

    # Get output of ffprobe in JSON format
    command = [
        "ffprobe",
        "-v",
        "quiet",
        "-print_format",
        "json",
        "-show_streams",
        video_file.url,
    ]

    process = await asyncio.create_subprocess_exec(
        *command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    stdout, stderr = await process.communicate()
    if process.returncode != 0:
        logger.error("probing viedo failed", video_id=video_id, strerr=stderr.decode())
        msg = "Probing video faild."
        raise InternalServerError(msg)

    # ffprobe output is in JSON
    # TODO: use pydantic objecst for parsing ffmpeg output -> This way we are sure of output format  # noqa: E501
    try:
        probe_data = orjson.loads(stdout)
    except JSONDecodeError as e:
        logger.exception(
            "couldn't parse json output for ffprobe",
            video_id=video_id,
            stdout=stdout,
            exc_info=e,
        )
        msg = "Parsing video probe data failed."
        raise InternalServerError(msg) from e

    streams = probe_data.get("streams", [])
    if not streams:
        logger.error("video has no streams", video_id=video_id, probe_data=probe_data)
        return

    # Continue only if first stream is of type video
    if streams[0].get("codec_type", "unknown") != "video":
        logger.error(
            "first stream of video is not a video stream",
            video_id=video_id,
            probe_data=probe_data,
        )
        return

    video_stream = streams[0]
    probe_data = VideoProbeDataSchema(
        video_id=video_id,
        video_file_key=video_file.key,
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

    # Update video duration
    logger.info(
        "updating video duration",
        video_id=video_id,
        duration_seconds=probe_data.duration_seconds,
    )
    await video_service.update(
        UpdateVideoSchema(id=video_id, duration_seconds=probe_data.duration_seconds)
    )

    # Generate jobs for video variants and store remaining count in redis
    # Each job will check if count reached 0 and therefore bento4 can start muxing
    logger.info("creating processing jobs for video", video_id=video_id)
    variants = await create_processing_jobs_for_video(probe_data)

    await redis.set(
        tvp.videos.cache_keys.video_remaining_processing_jobs_count(video_id=video_id),
        len(variants),
    )

    for v in variants:
        logger.info(
            "creating varient for video", video_id=video_id, variant_code=v.variant_code
        )
        await video_service.create_empty_variant(v)
        await process_variant.kiq(v.video_id, v.variant_code)  # ty:ignore[no-matching-overload]
