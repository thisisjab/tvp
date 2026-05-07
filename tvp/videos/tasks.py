import tempfile
from typing import TYPE_CHECKING, Any
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
    BatchUpdateVideoVariantState,
    CreateVideoVariantSchema,
    GetVideoVariantSchema,
    UpdateVariantSchema,
    UpdateVideoSchema,
    VideoProbeDataSchema,
    VideoSchema,
    VideoVariantSchema,
)
from tvp.videos.storage_keys import video_variant_storage_key
from tvp.videos.utils import run_subcommand

if TYPE_CHECKING:
    from tvp.files.schemas import FileSchema

logger = structlog.getLogger(__name__)


async def _create_fmp4(
    variant: VideoVariantSchema, fmp4_src_path: str, fmp4_output_path: str
) -> None:
    """Create fmp4 using bento4 and return output path."""
    logger.debug(
        "video variant downloaded", video_id=variant.video_id, path=fmp4_src_path
    )

    # Create fmp4
    create_fmp4_result = await run_subcommand(
        [
            "mp4fragment",
            fmp4_src_path,
            fmp4_output_path,
        ]
    )
    if not create_fmp4_result or create_fmp4_result.return_code != 0:
        logger.error(
            "cannot create fmp4",
            video_id=variant.video_id,
            variant_code=variant.variant_code,
            result=create_fmp4_result,
        )
        msg = "Cannot create fmp4."
        raise InternalServerError(msg)

    logger.info(
        "finished creating fmp4",
        video_id=variant.video_id,
        variant_code=variant.variant_code,
    )


@broker.task
async def generate_master_playlist(
    video_id: UUID,
    video_service: TaskiqVideoServiceDep,
    file_service: TaskiqFileServiceDep,
    redis: TaskiqRedisClient,
) -> None:
    """
    Check if there are no remaining tasks and start creating segments.
    After segments are created, they will be uploaded to storage.
    """  # noqa: D205
    video = await video_service.get_by_id(video_id)
    if not video:
        logger.error(
            "attempt to create master playlist with non existing video",
            video_id=video_id,
        )
        return

    # Only do the muxing (creating playlist) if all variants are ready
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
    if not variants:  # Weird if it happens, but let's check anyway
        logger.error(
            "attempt to create master playlist for a video with no variant",
            video_id=video_id,
        )
        return

    # Download varients
    with tempfile.TemporaryDirectory(delete=True) as working_dir:
        created_fmp4s = []

        for v in variants:
            # Download variant
            output_path = f"{working_dir}/{v.variant_code.value}.mp4"
            await file_service.download_to_path(v.file_id, output_path)  # ty:ignore[invalid-argument-type]

            fmp4_output_path = f"{working_dir}/f_{v.variant_code.value}.mp4"
            await _create_fmp4(
                v, fmp4_src_path=output_path, fmp4_output_path=fmp4_output_path
            )

            created_fmp4s.append(fmp4_output_path)

        # Update variants state to indicate they are being muxed
        await video_service.batch_update_variant_state(
            BatchUpdateVideoVariantState(
                video_id=video_id, state=VideoVariantProcessingState.MUXING
            )
        )

        # Create playlists
        hls_output_dir = f"{working_dir}/hls_output"
        hls_creation_result = await run_subcommand(
            [
                "mp4hls",
                f"--segment-duration={SEGMENT_LENGTH_SECONDS}",
                f"--output-dir={hls_output_dir}",
                *created_fmp4s,
            ]
        )
        if not hls_creation_result or hls_creation_result.return_code != 0:
            logger.error(
                "cannot create hls playlist",
                video_id=video_id,
                result=hls_creation_result,
            )

            # In case creating hls playlist failed, set muxing failed
            await video_service.batch_update_variant_state(
                BatchUpdateVideoVariantState(
                    video_id=video_id, state=VideoVariantProcessingState.MUXING_FAILED
                )
            )

            msg = "Cannot create hls playlist"
            raise InternalServerError(msg)

        # TODO: upload dir


def _build_ffmpeg_audio_transcode_params(
    video_variant: VideoVariantSchema,
) -> list[str]:
    return (
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


def _build_ffmpeg_video_transcode_params(
    video_variant: VideoVariantSchema,
) -> list[str]:
    return [
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


async def _transcode_video(
    video_variant: VideoVariantSchema, original_video_file_url: str, output_path: str
) -> None:
    """Transcode video based on probed data and return either if it the job succeeded or not."""  # noqa: E501
    cmd = [
        "ffmpeg",
        "-i",
        original_video_file_url,
        *_build_ffmpeg_video_transcode_params(video_variant),
        *_build_ffmpeg_audio_transcode_params(video_variant),
        "-movflags",
        "frag_keyframe+empty_moov+default_base_moof",
        "-f",
        "mp4",
        output_path,
    ]

    # TODO: add timeouts
    transcoding_result = await run_subcommand(cmd)
    if not transcoding_result or transcoding_result.return_code != 0:
        logger.error(
            "probing video failed",
            video_id=video_variant.video_id,
            result=transcoding_result,
        )
        msg = "Transcoding failed"
        raise InternalServerError(msg)


@broker.task
async def transcode_variant_task(
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

    # Update variant processing status
    await video_service.update_variant(
        UpdateVariantSchema(
            video_id=video_id,
            variant_code=variant_code,
            state=VideoVariantProcessingState.PROCESSING,
        )
    )

    with tempfile.TemporaryDirectory(delete=True) as output_dir:
        output_name = f"output-{variant_code.value}.mp4"
        output_path = f"{output_dir}/{output_name}"

        # Transcode video
        await _transcode_video(video_variant, video_file.url, output_path)

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

        # Create master playlist task will make sure that all tasks are finished
        # before proceeding. So this call is safe.
        await generate_master_playlist.kiq(video_id)  # ty:ignore[no-matching-overload]


async def _create_variants_from_probe_data(
    probe_data: VideoProbeDataSchema,
) -> list[CreateVideoVariantSchema]:
    """Check what variants can the video be transcoded to and create video variants."""
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


async def _get_video_streams(
    video_id: UUID, video_download_url: str
) -> list[dict[str, Any]]:
    """Use subprocess to get video streams info. using ffprobe."""
    # Get output of ffprobe in JSON format
    cmd = [
        "ffprobe",
        "-v",
        "quiet",
        "-print_format",
        "json",
        "-show_streams",
        video_download_url,
    ]

    probing_result = await run_subcommand(
        cmd,
    )

    if not probing_result or probing_result.return_code != 0:
        logger.error("probing viedo failed", video_id=video_id, result=probing_result)
        msg = "Probing video faild."
        raise InternalServerError(msg)

    # ffprobe output is in JSON
    # TODO: use pydantic objecst for parsing ffmpeg output -> This way we are sure of output format  # noqa: E501
    try:
        return orjson.loads(probing_result.stdout).get("streams", [])
    except JSONDecodeError as e:
        logger.exception(
            "couldn't parse json output for ffprobe",
            video_id=video_id,
            stdout=probing_result.stdout,
            exc_info=e,
        )
        msg = "Parsing video probe data failed."
        raise InternalServerError(msg) from e


async def _clean_probe_data(
    video_id: UUID, video_file_key: str, streams: list[dict]
) -> VideoProbeDataSchema | None:
    """Check if video has valid streams and return `VideoProbeDataSchema`."""
    if not streams:
        logger.error("video has no streams", video_id=video_id)
        return None

    # Continue only if first stream is of type video
    if streams[0].get("codec_type", "unknown") != "video":
        logger.error(
            "first stream of video is not a video stream",
            video_id=video_id,
            streams=streams,
        )
        return None

    video_stream = streams[0]
    probe_data = VideoProbeDataSchema(
        video_id=video_id,
        video_file_key=video_file_key,
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


@broker.task(retry_on_error=True, max_retries=3)
async def process_video_task(
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

    streams = await _get_video_streams(
        video_id=video_id, video_download_url=video_file.url
    )

    # Clean up probed data
    cleaned_probed_data = await _clean_probe_data(video_id, video_file.key, streams)
    if not cleaned_probed_data:
        logger.error("video probing failed", video_id=video_id)
        return

    # Update video duration
    logger.info(
        "updating video duration",
        video_id=video_id,
        duration_seconds=cleaned_probed_data.duration_seconds,
    )
    await video_service.update(
        UpdateVideoSchema(
            id=video_id, duration_seconds=cleaned_probed_data.duration_seconds
        )
    )

    # Generate jobs for video variants and store remaining count in redis
    # Each job will check if count reached 0 and therefore bento4 can start muxing
    logger.info("creating processing jobs for video", video_id=video_id)
    variants = await _create_variants_from_probe_data(cleaned_probed_data)
    await redis.set(
        tvp.videos.cache_keys.video_remaining_processing_jobs_count(video_id=video_id),
        len(variants),
    )

    # Trigger variant processing job which will transcode variant to a specific
    # bitrate and resolution
    for v in variants:
        logger.info(
            "creating varient for video", video_id=video_id, variant_code=v.variant_code
        )
        await video_service.create_variant(v)
        await transcode_variant_task.kiq(v.video_id, v.variant_code)  # ty:ignore[no-matching-overload]
