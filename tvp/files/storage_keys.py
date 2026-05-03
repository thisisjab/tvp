from uuid import UUID


def file_upload_key(mimetype: str, file_id: UUID, file_name: str) -> str:
    prefix = "unknown"

    if mimetype.startswith("image/"):
        prefix = "images"
    elif mimetype.startswith("video/"):
        prefix = "videos"

    return f"{prefix}/{file_id}-{file_name}"
