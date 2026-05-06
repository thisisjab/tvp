from uuid import UUID

from tvp.videos.constants import VideoVariantCode


def video_variant_storage_key(
    video_id: UUID | str, variant_code: VideoVariantCode, extension: str = "mp4"
) -> str:
    return f"videos/{video_id!s}/output_{variant_code.value!s}.{extension}"
