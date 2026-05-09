from fastapi import APIRouter

from tvp.users.deps import CurrentUserDep
from tvp.videos.deps import VideoServiceDep
from tvp.videos.schemas import (
    CreateVideoRequest,
    CreateVideoResponse,
    CreateVideoSchema,
    FinalizeVideoUploadRequest,
    FinalizeVideoUploadSchema,
    VideoSchema,
)

videos_router = APIRouter(tags=["Video"])


@videos_router.post("")
async def create_video(
    req: CreateVideoRequest, video_service: VideoServiceDep, user: CurrentUserDep
) -> CreateVideoResponse:
    """Create a video inside user's collection."""
    return await video_service.create_video(
        CreateVideoSchema(**req.model_dump(), owner_id=user.id)
    )


@videos_router.post("/finalize-upload")
async def finalize_video_upload(
    req: FinalizeVideoUploadRequest,
    video_service: VideoServiceDep,
    user: CurrentUserDep,
) -> VideoSchema:
    """Mark video as uploaded so that it can be processed and be ready for streaming."""
    return await video_service.finalize_video_upload(
        FinalizeVideoUploadSchema(
            user_id=user.id,
            token=req.token,
        )
    )
