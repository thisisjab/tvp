import tempfile
from uuid import UUID

import structlog

import tvp.videos.cache_keys
from tvp.errors import InternalServerError
from tvp.files.deps import TaskiqFileServiceDep
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
    VideoProcessingState,
    VideoVariantCode,
)
from tvp.videos.deps import TaskiqVideoServiceDep
from tvp.videos.schemas import (
    VideoTranscodingJobSchema,
)
from tvp.videos.storage_keys import (
    hls_dir_prefix,
    transcoded_video_storage_key,
    transcoded_videos_prefix,
    user_uploaded_video_storage_key,
)
from tvp.videos.utils import run_subcommand

logger = structlog.getLogger(__name__)


@broker.task(retry_on_error=True, max_retries=5)
async def generate_master_playlist(
    video_id: UUID,
    video_service: TaskiqVideoServiceDep,
    file_service: TaskiqFileServiceDep,
    redis: TaskiqRedisClient,
) -> None:
    """
    Check if there are no remaining tasks and start creating segments.
    After segments are created, they will be uploaded to storage. In addition
    user uploaded video will be removed from storage to save disk.
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

    # Update state
    await video_service.update_video_state(video_id, VideoProcessingState.MUXING)

    with tempfile.TemporaryDirectory(delete=False) as working_dir:
        # Download transcoded videos
        downloaded_transocoded_videos = []
        prefix = transcoded_videos_prefix(video_id)
        for f in file_service.list_objects(prefix):
            if f.is_dir:
                continue

            await file_service.download_to_path(f.key, f"{working_dir}/{f.name}")
            downloaded_transocoded_videos.append(f.key.removeprefix(f"{prefix}/"))

        # Create fmp4 for each video
        # out_480.mp4 -> f_out_490.mp4
        created_fmp4s = []
        for tv in downloaded_transocoded_videos:
            fmp4_output_path = f"{working_dir}/f_{tv}"
            create_fmp4_result = await run_subcommand(
                [
                    "mp4fragment",
                    f"{working_dir}/{tv}",
                    fmp4_output_path,
                ]
            )
            if not create_fmp4_result or create_fmp4_result.return_code != 0:
                logger.error(
                    "cannot create fmp4",
                    video_id=video_id,
                    result=create_fmp4_result,
                )
                msg = "Cannot create fmp4."
                raise InternalServerError(msg)

            logger.info(
                "finished creating fmp4",
                video_id=video_id,
                output=fmp4_output_path,
            )

            created_fmp4s.append(fmp4_output_path)

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

            await video_service.update_video_state(
                video_id, VideoProcessingState.MUXING_FAILED
            )

            msg = "Cannot create hls playlist"
            raise InternalServerError(msg)

        await file_service.upload_dir(
            path=hls_output_dir, prefix=hls_dir_prefix(video_id)
        )


def _build_ffmpeg_audio_transcode_params(
    video_variant: VideoTranscodingJobSchema,
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
    video_variant: VideoTranscodingJobSchema,
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


@broker.task(retry_on_error=True, max_retries=5)
async def transcode_video_task(
    job: VideoTranscodingJobSchema,
    video_service: TaskiqVideoServiceDep,
    file_service: TaskiqFileServiceDep,
    redis: TaskiqRedisClient,
) -> None:
    """Transcode video to mp4, store in storage, and fire muxing job.

    For more info., visit probe_video task.
    """
    video = await video_service.get_by_id(job.video_id)
    if not video:
        logger.error("video does not exist for transcoding", video_id=job.video_id)
        return

    await video_service.update_video_state(
        job.video_id, VideoProcessingState.TRANSCODING
    )

    # Generate download link
    video_download_link = await file_service.get_download_link(
        user_uploaded_video_storage_key(video_id=video.id, owner_id=video.owner_id)
    )

    with tempfile.TemporaryDirectory(delete=True) as output_dir:
        output_name = f"output-{job.variant_code.value}.mp4"
        output_path = f"{output_dir}/{output_name}"

        # Transcode video
        # TODO: add timeouts
        transcoding_result = await run_subcommand(
            [
                "ffmpeg",
                "-i",
                video_download_link,
                *_build_ffmpeg_video_transcode_params(job),
                *_build_ffmpeg_audio_transcode_params(job),
                "-movflags",
                "frag_keyframe+empty_moov+default_base_moof",
                "-f",
                "mp4",
                output_path,
            ]
        )
        if not transcoding_result or transcoding_result.return_code != 0:
            logger.error(
                "probing video failed",
                video_id=job.video_id,
                result=transcoding_result,
            )
            msg = "Transcoding failed"
            raise InternalServerError(msg)

        # Upload processed variant
        logger.info(
            "uploading variant", video_id=job.video_id, variant_code=job.variant_code
        )

        await file_service.upload_file_from_path(
            key=transcoded_video_storage_key(
                job.video_id,
                job.variant_code,
            ),
            path=output_path,
        )

        # Decrease number of remaining jobs
        async with RedisLock(
            redis, lock_video_remaining_processing_jobs_count(video_id=job.video_id)
        ):
            await redis.incrby(
                tvp.videos.cache_keys.video_remaining_processing_jobs_count(
                    video_id=job.video_id
                ),
                -1,
            )

        # Create master playlist task will make sure that all tasks are finished
        # before proceeding. So this call is safe.
        await generate_master_playlist.kiq(job.video_id)  # ty:ignore[no-matching-overload]


@broker.task(retry_on_error=True, max_retries=3)
async def create_processing_jobs(
    video_id: UUID,
    video_service: TaskiqVideoServiceDep,
    redis: TaskiqRedisClient,
) -> None:
    """Probe video then create transcoding tasks for processing possible resolutions of a video."""  # noqa: E501
    # Get probed data
    probed_data = await video_service.get_video_probed_data(video_id=video_id)

    ## Common values
    # Calculate FPS
    fps = min(probed_data.fps, MAX_ALLOWED_FPS)

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
            and (v.value <= probed_data.height)
        )
    ]
    # Generate jobs for video variants and store remaining count in redis
    # Each job will check if count reached 0 and therefore bento4 can start muxing
    transcoding_jobs = []
    for v in variants:
        video_bitrate = int(
            min(
                (probed_data.video_bitrate * (v.value / probed_data.height)),
                VIDEO_BITRATES[v],
            )
        )
        audio_bitrate = min(
            probed_data.audio_bitrate or 0,
            AUDIO_BITRATES[v],
        )

        transcoding_jobs.append(
            VideoTranscodingJobSchema(
                video_id=video_id,
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

    await redis.set(
        tvp.videos.cache_keys.video_remaining_processing_jobs_count(video_id=video_id),
        len(variants),
    )

    # Trigger variant processing job which will transcode variant to a specific
    # bitrate and resolution
    for j in transcoding_jobs:
        logger.info(
            "creating transcoding jobs for video",
            video_id=video_id,
        )
        await transcode_video_task.kiq(j)  # ty:ignore[no-matching-overload]
