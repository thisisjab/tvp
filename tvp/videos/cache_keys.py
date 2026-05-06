from uuid import UUID


def lock_video_remaining_processing_jobs_count(video_id: UUID | str) -> str:
    return f"lock:videos#{video_id!s}:remaining-processing-jobs-count"


def video_remaining_processing_jobs_count(video_id: UUID | str) -> str:
    return f"videos#{video_id!s}:remaining-processing-jobs-count"
