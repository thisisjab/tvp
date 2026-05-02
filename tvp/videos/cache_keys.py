from uuid import UUID


def video_probe_info(video_id: UUID | str) -> str:
    return f"videos#{video_id!s}:probe-info"
