from uuid import UUID


def video_probe_data_cache_key(video_id: UUID | str) -> str:
    return f"videos#{video_id!s}:probe_data"


def lock_video_remaining_processing_jobs_count(video_id: UUID | str) -> str:
    return f"lock:videos#{video_id!s}:remaining-processing-jobs-count"


def video_remaining_processing_jobs_count(video_id: UUID | str) -> str:
    return f"videos#{video_id!s}:remaining-processing-jobs-count"
