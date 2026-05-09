from uuid import UUID

from tvp.videos.constants import VideoVariantCode


def user_uploaded_video_storage_key(owner_id: UUID | str, video_id: UUID | str) -> str:
    """Key to upload user videos when videos are first created."""
    return f"videos/{owner_id!s}/{video_id!s}_not_processed"


def transcoded_videos_prefix(video_id: UUID | str) -> str:
    return f"videos/{video_id!s}/transcoded"


def transcoded_video_storage_key(
    video_id: UUID | str, variant_code: VideoVariantCode, extension: str = "mp4"
) -> str:
    return f"{transcoded_videos_prefix(video_id)}/{variant_code.value!s}.{extension}"


def hls_dir_prefix(video_id: UUID | str) -> str:
    return f"videos/{video_id!s}/hls"
