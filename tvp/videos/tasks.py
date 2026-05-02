import asyncio
import json
from uuid import UUID

import structlog
from minio.datatypes import JSONDecodeError

import tvp.videos.cache_keys
from tvp.errors import InternalServerError
from tvp.redis.deps import TaskiqRedisClient
from tvp.taskiq import broker
from tvp.videos.schemas import VideoProbeDataSchema

logger = structlog.getLogger(__name__)


@broker.task
async def store_video_info_in_redis(
    video_id: UUID,
    video_file_key: str,
    video_download_url: str,
    redis: TaskiqRedisClient,
) -> None:
    """Read properties of video using `ffprobe` and store in redis.

    Stored properties:
        - width
        - height
        - fps
        - video_bitrate
        - audio_bitrate
        - length

    These values will be used by workers to determine bitrate of final output.
    """
    # Get output of ffprobe in JSON format
    command = [
        "ffprobe",
        "-v",
        "quiet",
        "-print_format",
        "json",
        "-show_streams",
        video_download_url,
    ]

    process = await asyncio.create_subprocess_exec(
        *command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    stdout, stderr = await process.communicate()
    if stderr:
        logger.error("probing viedo failed", video_id=video_id, strerr=stderr.decode())
        msg = "Probing video faild."
        raise InternalServerError(msg)

    # ffprobe output is in JSON
    # TODO: use pydantic objecst for parsing ffmpeg output -> This way we are sure of output format  # noqa: E501
    try:
        probe_data = json.loads(stdout)
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
        msg = "Probing video failed."
        raise InternalServerError(msg)

    # Continue only if first stream is of type video
    if streams[0].get("codec_type", "unknown") != "video":
        logger.error(
            "first stream of video is not a video stream",
            video_id=video_id,
            probe_data=probe_data,
        )
        msg = "Processing video failed."
        raise InternalServerError(msg)

    video_stream = streams[0]
    video_data = VideoProbeDataSchema(
        video_id=video_id,
        video_file_key=video_file_key,
        width=video_stream.get("width"),
        height=video_stream.get("height"),
        duration_seconds=video_stream.get("duration"),
        # r_frame_rate is in form of x/y where x and y are integers
        # Schema class will handle conversion automatically
        fps=video_stream.get("r_frame_rate"),
        video_bitrate=int(video_stream.get("bitrate")),
    )

    # Find first audio stream to get its bitrate
    audio_streams = [
        s for s in streams[1:] if s.get("codec_type", "unknown") == "audio"
    ]
    if audio_streams:
        video_data.audio_bitrate = audio_streams[0].get("bitrate")

    # Store in redis
    await redis.set(
        name=tvp.videos.cache_keys.video_probe_info(video_id),
        value=video_data.model_dump(),
    )
